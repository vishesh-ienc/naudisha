"""
Geographic grid and navigational graph abstraction for ship routing.
Provides a spatial network layer modeling sea coordinates as nodes and directional segments as edges.
Directly integrates with NauDisha's CostModel to dynamically compute and update edge costs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    SegmentEvaluation,
)
from naudisha.cost.model import CostModel


@dataclass(frozen=True)
class GridConfig:
    """
    Configuration for creating a regular geographic navigation grid.

    Attributes:
        origin_lat: Reference origin latitude in degrees [-90.0, 90.0] (South/bottom boundary).
        origin_lon: Reference origin longitude in degrees [-180.0, 180.0] (West/left boundary).
        rows: Number of grid rows along latitude (must be >= 1).
        cols: Number of grid columns along longitude (must be >= 1).
        lat_spacing: Latitude step size in degrees between adjacent rows (> 0.0).
        lon_spacing: Longitude step size in degrees between adjacent columns (> 0.0).
    """
    origin_lat: float
    origin_lon: float
    rows: int
    cols: int
    lat_spacing: float
    lon_spacing: float

    def __post_init__(self) -> None:
        if self.rows <= 0:
            raise ValueError("rows must be a positive integer >= 1.")
        if self.cols <= 0:
            raise ValueError("cols must be a positive integer >= 1.")
        if self.lat_spacing <= 0:
            raise ValueError("lat_spacing must be positive.")
        if self.lon_spacing <= 0:
            raise ValueError("lon_spacing must be positive.")
        if not (-90.0 <= self.origin_lat <= 90.0):
            raise ValueError("origin_lat must be within [-90.0, 90.0].")
        if not (-180.0 <= self.origin_lon <= 180.0):
            raise ValueError("origin_lon must be within [-180.0, 180.0].")


@dataclass
class GridNode:
    """
    A geographic waypoint node in the maritime navigation grid.

    Attributes:
        node_id: Unique identifier string (e.g. 'node_0_0').
        row: Row index in the grid [0, rows-1].
        col: Column index in the grid [0, cols-1].
        lat: Geographic latitude in degrees.
        lon: Geographic longitude in degrees.
        is_navigable: Navigability flag (False indicates land, shallows, or restricted zone).
    """
    node_id: str
    row: int
    col: int
    lat: float
    lon: float
    is_navigable: bool = True


@dataclass
class GridEdge:
    """
    A directed navigational segment connecting two adjacent nodes in the grid.

    Attributes:
        source_id: Origin node ID.
        target_id: Destination node ID.
        segment: SegmentData containing geographic coordinates and navigability.
        env_data: Environmental conditions assigned to this segment.
        cost: Computed edge cost from CostModel (or math.inf if non-navigable).
        is_navigable: Edge navigability status.
        evaluation: Detailed SegmentEvaluation breakdown from CostModel.
    """
    source_id: str
    target_id: str
    segment: SegmentData
    env_data: Optional[EnvironmentalData] = None
    cost: float = math.inf
    is_navigable: bool = True
    evaluation: Optional[SegmentEvaluation] = None


class GeographicGridGraph:
    """
    Spatial navigation graph modeling a geographic grid with 4-direction movements (North, South, East, West).

    Features:
    - Directed edges reflecting directional ocean current/wind effects.
    - Full integration with NauDisha CostModel for edge evaluation.
    - $O(1)$ dynamic environmental and cost updates without graph reconstruction.
    - Complete query interfaces for D* Lite (successors, predecessors, costs, navigability).
    """

    # 4-Direction movement offsets: (d_row, d_col, direction_name)
    DIRECTIONS_4: List[Tuple[int, int, str]] = [
        (1, 0, "North"),
        (-1, 0, "South"),
        (0, 1, "East"),
        (0, -1, "West"),
    ]

    def __init__(
        self,
        config: GridConfig,
        cost_model: Optional[CostModel] = None,
        default_ship: Optional[ShipProfile] = None,
        default_weights: Optional[CostWeights] = None,
    ) -> None:
        self.config = config
        self.cost_model = cost_model or CostModel()
        self.default_ship = default_ship
        self.default_weights = default_weights or CostWeights()

        self._nodes: Dict[str, GridNode] = {}
        self._grid_lookup: Dict[Tuple[int, int], str] = {}  # (row, col) -> node_id
        self._edges: Dict[Tuple[str, str], GridEdge] = {}    # (source_id, target_id) -> GridEdge
        self._outgoing: Dict[str, Set[str]] = {}             # node_id -> set of target_ids
        self._incoming: Dict[str, Set[str]] = {}             # node_id -> set of source_ids

        self._build_grid()

    def _build_grid(self) -> None:
        """Constructs nodes and 4-connected directed edges for the grid."""
        # 1. Create Nodes
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                lat = self.config.origin_lat + r * self.config.lat_spacing
                lon = self.config.origin_lon + c * self.config.lon_spacing
                node_id = f"node_{r}_{c}"

                node = GridNode(
                    node_id=node_id,
                    row=r,
                    col=c,
                    lat=lat,
                    lon=lon,
                    is_navigable=True,
                )
                self._nodes[node_id] = node
                self._grid_lookup[(r, c)] = node_id
                self._outgoing[node_id] = set()
                self._incoming[node_id] = set()

        # 2. Create 4-direction directed edges
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                source_id = self._grid_lookup[(r, c)]
                source_node = self._nodes[source_id]

                for dr, dc, _ in self.DIRECTIONS_4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.config.rows and 0 <= nc < self.config.cols:
                        target_id = self._grid_lookup[(nr, nc)]
                        target_node = self._nodes[target_id]

                        segment = SegmentData(
                            start_lat=source_node.lat,
                            start_lon=source_node.lon,
                            end_lat=target_node.lat,
                            end_lon=target_node.lon,
                            is_navigable=True,
                        )
                        edge = GridEdge(
                            source_id=source_id,
                            target_id=target_id,
                            segment=segment,
                            env_data=None,
                            cost=math.inf,
                            is_navigable=True,
                        )
                        self._edges[(source_id, target_id)] = edge
                        self._outgoing[source_id].add(target_id)
                        self._incoming[target_id].add(source_id)

    # -------------------------------------------------------------------------
    # Node Queries
    # -------------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[GridNode]:
        """Retrieves a node by its unique identifier."""
        return self._nodes.get(node_id)

    def get_node_by_coords(self, row: int, col: int) -> Optional[GridNode]:
        """Retrieves a node by its grid row and column indices."""
        node_id = self._grid_lookup.get((row, col))
        if node_id:
            return self._nodes.get(node_id)
        return None

    def get_all_nodes(self) -> List[GridNode]:
        """Returns a list of all nodes in the graph."""
        return list(self._nodes.values())

    def is_node_navigable(self, node_id: str) -> bool:
        """Returns True if the node exists and is navigable."""
        node = self._nodes.get(node_id)
        return bool(node and node.is_navigable)

    def set_node_navigability(
        self,
        node_id: str,
        is_navigable: bool,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> None:
        """
        Updates the navigability of a node (e.g. marking an obstacle/landmass).
        Automatically updates all incident edges (incoming and outgoing).
        """
        node = self._nodes.get(node_id)
        if not node:
            raise KeyError(f"Node '{node_id}' not found in graph.")

        node.is_navigable = is_navigable

        # Recalculate or disable outgoing edges
        for target_id in self._outgoing.get(node_id, set()):
            self.recalculate_edge_cost(node_id, target_id, ship=ship, weights=weights)

        # Recalculate or disable incoming edges
        for source_id in self._incoming.get(node_id, set()):
            self.recalculate_edge_cost(source_id, node_id, ship=ship, weights=weights)

    # -------------------------------------------------------------------------
    # Edge Queries
    # -------------------------------------------------------------------------

    def get_edge(self, source_id: str, target_id: str) -> Optional[GridEdge]:
        """Retrieves the directed edge connecting source_id to target_id."""
        return self._edges.get((source_id, target_id))

    def get_all_edges(self) -> List[GridEdge]:
        """Returns a list of all directed edges in the graph."""
        return list(self._edges.values())

    def get_edge_cost(self, source_id: str, target_id: str) -> float:
        """
        Retrieves the traversal cost from source_id to target_id.
        Returns math.inf if the edge does not exist or is non-navigable.
        """
        edge = self._edges.get((source_id, target_id))
        if edge is None:
            return math.inf
        return edge.cost

    def is_edge_navigable(self, source_id: str, target_id: str) -> bool:
        """Returns True if the edge exists, both end nodes are navigable, and edge is navigable."""
        edge = self._edges.get((source_id, target_id))
        if not edge or not edge.is_navigable:
            return False
        return self.is_node_navigable(source_id) and self.is_node_navigable(target_id)

    # -------------------------------------------------------------------------
    # Neighbor / Successor / Predecessor Queries for D* Lite
    # -------------------------------------------------------------------------

    def get_neighbors(self, node_id: str) -> List[GridNode]:
        """
        Returns list of reachable neighboring nodes (outgoing successors) from node_id.
        Equivalent to get_successors.
        """
        return self.get_successors(node_id)

    def get_successors(self, node_id: str) -> List[GridNode]:
        """Returns list of outgoing successor nodes reachable from node_id."""
        target_ids = self._outgoing.get(node_id, set())
        return [self._nodes[tid] for tid in target_ids if tid in self._nodes]

    def get_predecessors(self, node_id: str) -> List[GridNode]:
        """Returns list of incoming predecessor nodes that can reach node_id."""
        source_ids = self._incoming.get(node_id, set())
        return [self._nodes[sid] for sid in source_ids if sid in self._nodes]

    def get_outgoing_edges(self, node_id: str) -> List[GridEdge]:
        """Returns all directed edges originating from node_id."""
        target_ids = self._outgoing.get(node_id, set())
        return [self._edges[(node_id, tid)] for tid in target_ids if (node_id, tid) in self._edges]

    def get_incoming_edges(self, node_id: str) -> List[GridEdge]:
        """Returns all directed edges pointing into node_id."""
        source_ids = self._incoming.get(node_id, set())
        return [self._edges[(sid, node_id)] for sid in source_ids if (sid, node_id) in self._edges]

    # -------------------------------------------------------------------------
    # Dynamic Environmental and Cost Recalculation
    # -------------------------------------------------------------------------

    def recalculate_edge_cost(
        self,
        source_id: str,
        target_id: str,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> float:
        """
        Recalculates the cost of a single directed edge using the CostModel in O(1) time.

        Args:
            source_id: Origin node identifier.
            target_id: Destination node identifier.
            ship: Optional vessel profile (falls back to default_ship).
            weights: Optional cost weights (falls back to default_weights).

        Returns:
            Computed edge cost (or math.inf if non-navigable).
        """
        edge = self._edges.get((source_id, target_id))
        if not edge:
            raise KeyError(f"Edge from '{source_id}' to '{target_id}' does not exist.")

        source_node = self._nodes.get(source_id)
        target_node = self._nodes.get(target_id)

        # If either endpoint is non-navigable, edge is non-navigable
        if not source_node or not target_node or not source_node.is_navigable or not target_node.is_navigable:
            edge.is_navigable = False
            edge.cost = math.inf
            edge.evaluation = None
            return math.inf

        # If no environmental data is set, edge cost remains uninitialized (infinite)
        if edge.env_data is None:
            edge.cost = math.inf
            return math.inf

        vessel = ship or self.default_ship
        if vessel is None:
            raise ValueError(
                "A ShipProfile must be provided either in recalculate_edge_cost or as graph default_ship."
            )

        w = weights or self.default_weights

        # Update segment navigation state
        segment = SegmentData(
            start_lat=source_node.lat,
            start_lon=source_node.lon,
            end_lat=target_node.lat,
            end_lon=target_node.lon,
            is_navigable=True,
        )

        evaluation = self.cost_model.evaluate_segment(
            segment=segment,
            ship=vessel,
            env=edge.env_data,
            weights=w,
        )

        edge.segment = segment
        edge.evaluation = evaluation
        edge.is_navigable = evaluation.is_navigable
        edge.cost = evaluation.total_cost

        return edge.cost

    def update_edge_environment(
        self,
        source_id: str,
        target_id: str,
        env: EnvironmentalData,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> float:
        """
        Updates the environmental conditions on a specific directed edge and immediately recalculates its cost.
        Executes in O(1) time without modifying or rebuilding any other graph components.

        Args:
            source_id: Origin node ID.
            target_id: Destination node ID.
            env: Updated meteorological/oceanographic conditions.
            ship: Optional vessel profile.
            weights: Optional cost weights.

        Returns:
            The updated edge cost.
        """
        edge = self._edges.get((source_id, target_id))
        if not edge:
            raise KeyError(f"Edge from '{source_id}' to '{target_id}' does not exist.")

        edge.env_data = env
        return self.recalculate_edge_cost(source_id, target_id, ship=ship, weights=weights)

    def populate_uniform_environment(
        self,
        env: EnvironmentalData,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> None:
        """
        Initializes or sets uniform environmental conditions across all edges in the grid and computes costs.

        Args:
            env: Baseline environmental data.
            ship: Vessel profile.
            weights: Cost weights.
        """
        vessel = ship or self.default_ship
        w = weights or self.default_weights

        for (source_id, target_id), edge in self._edges.items():
            edge.env_data = env
            self.recalculate_edge_cost(source_id, target_id, ship=vessel, weights=w)
