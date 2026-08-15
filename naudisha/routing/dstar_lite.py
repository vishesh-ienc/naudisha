"""
D* Lite dynamic path planning engine (Interface / Future Roadmap).
D* Lite performs incremental graph search to rapidly replan optimal maritime routes
when environmental forecasts (weather, currents, hazards) change dynamically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from naudisha.core.models import SegmentData, ShipProfile


@dataclass(frozen=True)
class NavNode:
    """A geographic waypoint or grid node in the maritime navigational graph."""
    node_id: str
    lat: float
    lon: float


@dataclass(frozen=True)
class NavEdge:
    """A directed edge between two navigation nodes."""
    source_id: str
    target_id: str
    segment: SegmentData


class RoutingEngine(ABC):
    """Abstract interface for maritime pathfinding and dynamic routing engines."""

    @abstractmethod
    def plan_route(
        self,
        start_node: NavNode,
        goal_node: NavNode,
        ship: ShipProfile,
    ) -> List[NavNode]:
        """Calculates initial optimal route from start to goal."""
        pass

    @abstractmethod
    def update_edge_cost(
        self,
        edge: NavEdge,
        new_cost: float,
    ) -> None:
        """Dynamically updates an edge cost when environmental forecast changes."""
        pass

    @abstractmethod
    def replan(self, current_node: NavNode) -> List[NavNode]:
        """Incrementally updates and repairs the remaining path to goal using D* Lite."""
        pass


class DStarLiteRouter(RoutingEngine):
    """
    D* Lite incremental heuristic search routing engine.
    (To be implemented in subsequent project phase).
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, NavNode] = {}
        self.edges: Dict[Tuple[str, str], NavEdge] = {}

    def plan_route(
        self,
        start_node: NavNode,
        goal_node: NavNode,
        ship: ShipProfile,
    ) -> List[NavNode]:
        raise NotImplementedError("D* Lite route planning will be implemented in the next phase.")

    def update_edge_cost(
        self,
        edge: NavEdge,
        new_cost: float,
    ) -> None:
        raise NotImplementedError("Dynamic edge cost updates will be implemented in the next phase.")

    def replan(self, current_node: NavNode) -> List[NavNode]:
        raise NotImplementedError("Dynamic incremental replanning will be implemented in the next phase.")
