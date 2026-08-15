"""
Geographic grid and navigational graph abstraction for ship routing.
Provides a spatial network layer modeling sea coordinates as nodes and directional segments as edges.
Directly integrates with NauDisha's CostModel to dynamically compute and update edge costs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    SegmentEvaluation,
)
from naudisha.cost.model import CostModel
from naudisha.data.weather_provider import WeatherProvider, BatchCapableProvider, ConditionRequest


class GridEnvironmentUpdateError(Exception):
    """Raised when an environmental data provider fails during graph initialization or edge refresh."""
    pass


@dataclass
class EdgeRefreshResult:
    """
    Records the before-and-after state of a single directed edge after a selective environment refresh.

    Used by the routing layer to determine which edges changed and by how much, so that
    D* Lite can be notified of exactly the affected source vertices via update_edge() without
    rebuilding the graph or resetting planner state.

    Attributes:
        source_id: Origin node ID of the directed edge.
        target_id: Destination node ID of the directed edge.
        old_cost: Edge traversal cost before the refresh (math.inf if uninitialized or non-navigable).
        new_cost: Edge traversal cost after the refresh (math.inf if non-navigable after update).
        old_env: EnvironmentalData assigned before the refresh (None if uninitialized).
        new_env: EnvironmentalData assigned after the refresh.
    """
    source_id: str
    target_id: str
    old_cost: float
    new_cost: float
    old_env: Optional[EnvironmentalData]
    new_env: Optional[EnvironmentalData]


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
        environment_provider: Optional[WeatherProvider] = None,
    ) -> None:
        self.config = config
        self.cost_model = cost_model or CostModel()
        self.default_ship = default_ship
        self.default_weights = default_weights or CostWeights()
        self.environment_provider = environment_provider

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

    def get_edge_midpoint(self, source_id: str, target_id: str) -> Tuple[float, float]:
        """
        Calculates the geographic midpoint (latitude, longitude) between source and target nodes.

        Strategy rationale:
            Sampling environmental conditions at the segment midpoint provides a balanced,
            spatially representative approximation of the atmospheric and hydrodynamic regime
            encountered by the vessel across the transit between the two waypoints.

        Args:
            source_id: Origin node ID.
            target_id: Destination node ID.

        Returns:
            (midpoint_lat, midpoint_lon) in degrees.
        """
        source_node = self._nodes.get(source_id)
        target_node = self._nodes.get(target_id)
        if not source_node or not target_node:
            raise KeyError(f"Invalid edge '{source_id}' -> '{target_id}'.")
        mid_lat = (source_node.lat + target_node.lat) / 2.0
        mid_lon = (source_node.lon + target_node.lon) / 2.0
        return (mid_lat, mid_lon)

    def populate_environment(
        self,
        timestamp: Union[datetime, str],
        provider: Optional[WeatherProvider] = None,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> None:
        """
        Populates environmental conditions across all navigable directed edges in the grid
        by querying the injected or supplied WeatherProvider at each edge's geographic midpoint.

        Batch path (preferred):
            If the provider implements BatchCapableProvider, all midpoint requests are
            collected into a single batch call, yielding O(1) or O(T) remote requests
            for a grid with T distinct timestamps (typically 1).

        Fallback path:
            Providers that do not implement BatchCapableProvider are served using the
            original per-edge loop, preserving full backward compatibility.

        Args:
            timestamp: Explicit observation/forecast UTC timestamp (string or datetime).
            provider: Optional WeatherProvider (falls back to self.environment_provider).
            ship: Optional vessel profile (falls back to self.default_ship).
            weights: Optional cost weights (falls back to self.default_weights).

        Raises:
            ValueError: If no provider is supplied or configured.
            GridEnvironmentUpdateError: If the provider fails to fetch valid conditions.
        """
        active_provider = provider or self.environment_provider
        if active_provider is None:
            raise ValueError(
                "A WeatherProvider must be provided either to populate_environment() "
                "or configured as graph environment_provider."
            )

        vessel = ship or self.default_ship
        w = weights or self.default_weights

        # Identify all navigable edges and compute their midpoints
        navigable_edges: List[Tuple[str, str]] = []
        non_navigable_edges: List[Tuple[str, str]] = []
        for (source_id, target_id) in list(self._edges.keys()):
            source_node = self._nodes.get(source_id)
            target_node = self._nodes.get(target_id)
            if (
                not source_node or not target_node
                or not source_node.is_navigable or not target_node.is_navigable
            ):
                non_navigable_edges.append((source_id, target_id))
            else:
                navigable_edges.append((source_id, target_id))

        # Mark non-navigable edges immediately
        for source_id, target_id in non_navigable_edges:
            edge = self._edges[(source_id, target_id)]
            edge.is_navigable = False
            edge.cost = math.inf
            edge.evaluation = None

        if not navigable_edges:
            return

        # ---- Batch path ----
        if isinstance(active_provider, BatchCapableProvider):
            requests = [
                ConditionRequest(
                    lat=self.get_edge_midpoint(src, tgt)[0],
                    lon=self.get_edge_midpoint(src, tgt)[1],
                    timestamp=timestamp,
                )
                for src, tgt in navigable_edges
            ]
            try:
                batch_results = active_provider.fetch_conditions_batch(requests)
            except Exception as exc:
                raise GridEnvironmentUpdateError(
                    f"Batch environmental fetch failed during populate_environment(): {exc}"
                ) from exc

            for (source_id, target_id), req in zip(navigable_edges, requests):
                env = batch_results.get(req)
                if env is None:
                    raise GridEnvironmentUpdateError(
                        f"Batch fetch returned no result for edge '{source_id}' -> '{target_id}'."
                    )
                edge = self._edges[(source_id, target_id)]
                edge.env_data = env
                self.recalculate_edge_cost(source_id, target_id, ship=vessel, weights=w)
            return

        # ---- Per-edge fallback path (providers without BatchCapableProvider) ----
        for source_id, target_id in navigable_edges:
            mid_lat, mid_lon = self.get_edge_midpoint(source_id, target_id)
            try:
                env = active_provider.fetch_conditions(lat=mid_lat, lon=mid_lon, timestamp=timestamp)
            except Exception as exc:
                raise GridEnvironmentUpdateError(
                    f"Failed to fetch environmental data for edge '{source_id}' -> '{target_id}' "
                    f"at sampling midpoint ({mid_lat:.4f}N, {mid_lon:.4f}E) for timestamp '{timestamp}': {exc}"
                ) from exc
            edge = self._edges[(source_id, target_id)]
            edge.env_data = env
            self.recalculate_edge_cost(source_id, target_id, ship=vessel, weights=w)

    def refresh_edges(
        self,
        edges: List[Tuple[str, str]],
        timestamp: Union[datetime, str],
        provider: Optional[WeatherProvider] = None,
        ship: Optional[ShipProfile] = None,
        weights: Optional[CostWeights] = None,
    ) -> List[EdgeRefreshResult]:
        """
        Selectively refreshes environmental conditions and recalculates costs in O(1) time
        for a specific subset of directed edges.

        Returns one EdgeRefreshResult per requested edge recording the old and new cost and
        environmental state. The routing layer uses this to call dstar.update_edge() on exactly
        the edges whose costs changed, without rebuilding the graph or resetting planner state.

        Batch path (preferred for multi-edge refresh):
            If provider implements BatchCapableProvider and len(edges) > 1,
            all midpoint requests are collected and served by one bbox call.

        Fallback path:
            Per-edge fetching for providers without BatchCapableProvider, or single-edge refresh.

        Args:
            edges: List of directed edge pairs [(source_id, target_id), ...].
            timestamp: Explicit observation/forecast UTC timestamp.
            provider: Optional WeatherProvider (falls back to self.environment_provider).
            ship: Optional vessel profile (falls back to self.default_ship).
            weights: Optional cost weights (falls back to self.default_weights).

        Returns:
            List[EdgeRefreshResult]: One result per requested edge with old/new cost and env.

        Raises:
            KeyError: If any specified edge does not exist in the graph.
            GridEnvironmentUpdateError: If the provider fails for any refreshed edge.
        """
        active_provider = provider or self.environment_provider
        if active_provider is None:
            raise ValueError(
                "A WeatherProvider must be provided either to refresh_edges() "
                "or configured as graph environment_provider."
            )

        vessel = ship or self.default_ship
        w = weights or self.default_weights

        results: List[EdgeRefreshResult] = []

        # Validate all edges exist upfront
        for source_id, target_id in edges:
            if (source_id, target_id) not in self._edges:
                raise KeyError(f"Edge from '{source_id}' to '{target_id}' does not exist in graph.")

        # ---- Batch path for multi-edge refresh with capable provider ----
        if len(edges) > 1 and isinstance(active_provider, BatchCapableProvider):
            # Capture pre-refresh state and identify navigable/non-navigable
            navigable_refresh: List[Tuple[str, str]] = []
            for source_id, target_id in edges:
                edge = self._edges[(source_id, target_id)]
                old_cost = edge.cost
                old_env = edge.env_data
                source_node = self._nodes.get(source_id)
                target_node = self._nodes.get(target_id)
                if (
                    not source_node or not target_node
                    or not source_node.is_navigable or not target_node.is_navigable
                ):
                    edge.is_navigable = False
                    edge.cost = math.inf
                    edge.evaluation = None
                    results.append(EdgeRefreshResult(
                        source_id=source_id,
                        target_id=target_id,
                        old_cost=old_cost,
                        new_cost=math.inf,
                        old_env=old_env,
                        new_env=old_env,
                    ))
                else:
                    navigable_refresh.append((source_id, target_id))
                    # Store pre-refresh state for later
                    edge._pre_refresh_cost = old_cost
                    edge._pre_refresh_env = old_env

            if navigable_refresh:
                requests = [
                    ConditionRequest(
                        lat=self.get_edge_midpoint(src, tgt)[0],
                        lon=self.get_edge_midpoint(src, tgt)[1],
                        timestamp=timestamp,
                    )
                    for src, tgt in navigable_refresh
                ]
                try:
                    batch_results = active_provider.fetch_conditions_batch(requests)
                except Exception as exc:
                    raise GridEnvironmentUpdateError(
                        f"Batch environmental fetch failed during refresh_edges(): {exc}"
                    ) from exc

                for (source_id, target_id), req in zip(navigable_refresh, requests):
                    edge = self._edges[(source_id, target_id)]
                    old_cost = edge._pre_refresh_cost
                    old_env = edge._pre_refresh_env
                    env = batch_results.get(req)
                    if env is None:
                        raise GridEnvironmentUpdateError(
                            f"Batch fetch returned no result for edge '{source_id}' -> '{target_id}'."
                        )
                    edge.env_data = env
                    new_cost = self.recalculate_edge_cost(source_id, target_id, ship=vessel, weights=w)
                    results.append(EdgeRefreshResult(
                        source_id=source_id,
                        target_id=target_id,
                        old_cost=old_cost,
                        new_cost=new_cost,
                        old_env=old_env,
                        new_env=env,
                    ))
            return results

        # ---- Per-edge fallback path ----
        for source_id, target_id in edges:
            edge = self._edges.get((source_id, target_id))

            # Capture pre-refresh state
            old_cost = edge.cost
            old_env = edge.env_data

            source_node = self._nodes.get(source_id)
            target_node = self._nodes.get(target_id)
            if not source_node or not target_node or not source_node.is_navigable or not target_node.is_navigable:
                edge.is_navigable = False
                edge.cost = math.inf
                edge.evaluation = None
                results.append(EdgeRefreshResult(
                    source_id=source_id,
                    target_id=target_id,
                    old_cost=old_cost,
                    new_cost=math.inf,
                    old_env=old_env,
                    new_env=old_env,  # env unchanged when node is non-navigable
                ))
                continue

            mid_lat, mid_lon = self.get_edge_midpoint(source_id, target_id)

            try:
                env = active_provider.fetch_conditions(lat=mid_lat, lon=mid_lon, timestamp=timestamp)
            except Exception as exc:
                # Graph state is NOT modified on failure -- old_cost and old_env are preserved.
                raise GridEnvironmentUpdateError(
                    f"Failed to refresh environmental data for edge '{source_id}' -> '{target_id}' "
                    f"at sampling midpoint ({mid_lat:.4f}N, {mid_lon:.4f}E) for timestamp '{timestamp}': {exc}"
                ) from exc

            edge.env_data = env
            new_cost = self.recalculate_edge_cost(source_id, target_id, ship=vessel, weights=w)

            results.append(EdgeRefreshResult(
                source_id=source_id,
                target_id=target_id,
                old_cost=old_cost,
                new_cost=new_cost,
                old_env=old_env,
                new_env=env,
            ))

        return results

