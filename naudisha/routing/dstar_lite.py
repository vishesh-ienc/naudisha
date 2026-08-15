"""
D* Lite dynamic path planning engine for maritime routing.
Implements the incremental heuristic search algorithm by Koenig & Likhachev.
D* Lite plans backwards from goal to start, enabling fast, incremental route repair
when environmental conditions (currents, waves, winds, obstacles) change dynamically.
"""

from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Set, Tuple

from naudisha.core.calculations import calculate_haversine_distance
from naudisha.routing.graph import GeographicGridGraph, GridNode, GridEdge


class PriorityQueue:
    """
    Min-Priority Queue supporting efficient decrease-key and lazy deletion operations.
    Entries are ordered lexicographically by key tuple (k1, k2).
    """

    def __init__(self) -> None:
        self._heap: List[Tuple[float, float, int, str]] = []
        self._keys: Dict[str, Tuple[float, float]] = {}
        self._counter: int = 0  # Tie-breaker for stable ordering

    def __len__(self) -> int:
        return len(self._keys)

    def is_empty(self) -> bool:
        return len(self._keys) == 0

    def contains(self, item: str) -> bool:
        return item in self._keys

    def insert(self, item: str, key: Tuple[float, float]) -> None:
        """Inserts or updates an item with a new priority key."""
        self._keys[item] = key
        self._counter += 1
        heapq.heappush(self._heap, (key[0], key[1], self._counter, item))

    def remove(self, item: str) -> None:
        """Removes an item from the queue."""
        if item in self._keys:
            del self._keys[item]

    def top_key(self) -> Tuple[float, float]:
        """Returns the minimal key in the queue without popping. Returns (inf, inf) if empty."""
        self._clean_top()
        if not self._heap:
            return (math.inf, math.inf)
        return (self._heap[0][0], self._heap[0][1])

    def top(self) -> Optional[str]:
        """Returns the item with minimal key without popping."""
        self._clean_top()
        if not self._heap:
            return None
        return self._heap[0][3]

    def pop(self) -> Optional[str]:
        """Pops and returns the item with the smallest key."""
        self._clean_top()
        if not self._heap:
            return None
        k1, k2, _, item = heapq.heappop(self._heap)
        if item in self._keys and self._keys[item] == (k1, k2):
            del self._keys[item]
        return item

    def _clean_top(self) -> None:
        """Discards outdated or deleted entries from the top of the heap (lazy deletion)."""
        while self._heap:
            k1, k2, _, item = self._heap[0]
            if item in self._keys and self._keys[item] == (k1, k2):
                break
            heapq.heappop(self._heap)


class DStarLite:
    """
    Incremental heuristic dynamic path planner using the optimized D* Lite algorithm.

    Attributes:
        graph: The spatial navigation graph (GeographicGridGraph).
        start_id: Identifier of the origin waypoint.
        goal_id: Identifier of the destination waypoint.
        heuristic_scale: Scaling factor for the distance heuristic (default 0.0 = dynamic Dijkstra).
    """

    def __init__(
        self,
        graph: GeographicGridGraph,
        start_id: str,
        goal_id: str,
        heuristic_scale: float = 0.0,
    ) -> None:
        self.graph = graph
        self.start_id = start_id
        self.goal_id = goal_id
        self.last_start_id = start_id
        self.heuristic_scale = max(0.0, float(heuristic_scale))

        if not self.graph.get_node(start_id):
            raise KeyError(f"Start node '{start_id}' not found in navigation graph.")
        if not self.graph.get_node(goal_id):
            raise KeyError(f"Goal node '{goal_id}' not found in navigation graph.")

        # D* Lite state variables
        self.km: float = 0.0
        self.g: Dict[str, float] = {}
        self.rhs: Dict[str, float] = {}
        self.open_queue = PriorityQueue()

        # Diagnostics / statistics tracking
        self.expansions_count: int = 0

        self._initialize()

    def _initialize(self) -> None:
        """Initializes D* Lite search structures."""
        self.open_queue = PriorityQueue()
        self.km = 0.0
        self.g.clear()
        self.rhs.clear()
        self.last_start_id = self.start_id
        self.expansions_count = 0

        # In D* Lite, all nodes implicitly have g = inf, rhs = inf
        # Goal node starts with rhs(s_goal) = 0.0
        self.rhs[self.goal_id] = 0.0
        key = self.calculate_key(self.goal_id)
        self.open_queue.insert(self.goal_id, key)

    def heuristic(self, from_id: str, to_id: str) -> float:
        """
        Admissible and consistent great-circle distance heuristic.
        Calculates Haversine distance in nautical miles scaled by heuristic_scale.
        """
        if from_id == to_id or self.heuristic_scale <= 0.0:
            return 0.0

        n1 = self.graph.get_node(from_id)
        n2 = self.graph.get_node(to_id)
        if not n1 or not n2:
            return 0.0

        dist_nm = calculate_haversine_distance(n1.lat, n1.lon, n2.lat, n2.lon, unit="nm")
        return dist_nm * self.heuristic_scale

    def calculate_key(self, u: str) -> Tuple[float, float]:
        """
        Calculates lexicographical priority key for vertex u:
        k(u) = [min(g(u), rhs(u)) + h(s_start, u) + km, min(g(u), rhs(u))]
        """
        g_val = self.g.get(u, math.inf)
        rhs_val = self.rhs.get(u, math.inf)
        min_val = min(g_val, rhs_val)

        if math.isinf(min_val):
            return (math.inf, math.inf)

        k1 = min_val + self.heuristic(self.start_id, u) + self.km
        k2 = min_val
        return (k1, k2)

    def update_vertex(self, u: str) -> None:
        """
        Updates the lookahead value rhs(u) and maintains queue membership.

        If u != goal:
            rhs(u) = min_{s' in Succ(u)} ( c(u, s') + g(s') )
        """
        if u != self.goal_id:
            min_rhs = math.inf
            for succ in self.graph.get_successors(u):
                v = succ.node_id
                edge_cost = self.graph.get_edge_cost(u, v)
                g_v = self.g.get(v, math.inf)
                if not math.isinf(edge_cost) and not math.isinf(g_v):
                    val = edge_cost + g_v
                    if val < min_rhs:
                        min_rhs = val
            self.rhs[u] = min_rhs

        # Remove from queue if present
        if self.open_queue.contains(u):
            self.open_queue.remove(u)

        # Re-insert if locally inconsistent (g != rhs)
        g_u = self.g.get(u, math.inf)
        rhs_u = self.rhs.get(u, math.inf)
        if not math.isclose(g_u, rhs_u, abs_tol=1e-9):
            key = self.calculate_key(u)
            self.open_queue.insert(u, key)

    def compute_shortest_path(self) -> bool:
        """
        Executes incremental search to repair shortest paths until start vertex is consistent.
        Returns True if a valid path exists, False if goal is unreachable.
        """
        start_key = self.calculate_key(self.start_id)

        while (
            self.open_queue.top_key() < start_key
            or not math.isclose(
                self.rhs.get(self.start_id, math.inf),
                self.g.get(self.start_id, math.inf),
                abs_tol=1e-9,
            )
        ):
            if self.open_queue.is_empty():
                break

            k_old = self.open_queue.top_key()
            u = self.open_queue.pop()
            if u is None:
                break

            self.expansions_count += 1
            k_new = self.calculate_key(u)

            if k_old < k_new:
                # Key increased, re-insert with new key
                self.open_queue.insert(u, k_new)
            elif self.g.get(u, math.inf) > self.rhs.get(u, math.inf):
                # Locally overconsistent: cost decreased or newly discovered
                self.g[u] = self.rhs.get(u, math.inf)
                for pred in self.graph.get_predecessors(u):
                    self.update_vertex(pred.node_id)
            else:
                # Locally underconsistent: cost increased
                self.g[u] = math.inf
                self.update_vertex(u)
                for pred in self.graph.get_predecessors(u):
                    self.update_vertex(pred.node_id)

            start_key = self.calculate_key(self.start_id)

        # Path exists if start has finite cost estimate
        return not math.isinf(self.g.get(self.start_id, math.inf))

    def plan(self) -> List[str]:
        """
        Computes initial route from start to goal.
        Returns ordered list of node IDs forming the shortest path.
        """
        self.compute_shortest_path()
        return self.get_path()

    def get_path(self) -> List[str]:
        """
        Extracts the shortest path from current start to goal by greedily following min(c(u, s') + g(s')).
        Returns empty list [] if goal is unreachable.
        """
        g_start = self.g.get(self.start_id, math.inf)
        rhs_start = self.rhs.get(self.start_id, math.inf)

        if math.isinf(g_start) and math.isinf(rhs_start):
            return []

        path = [self.start_id]
        current = self.start_id
        visited: Set[str] = {current}

        while current != self.goal_id:
            best_succ = None
            best_val = math.inf

            for succ in self.graph.get_successors(current):
                v = succ.node_id
                edge_cost = self.graph.get_edge_cost(current, v)
                g_v = self.g.get(v, math.inf)

                if math.isinf(edge_cost) or math.isinf(g_v):
                    continue

                val = edge_cost + g_v
                if val < best_val:
                    best_val = val
                    best_succ = v

            if best_succ is None or math.isinf(best_val):
                # Dead end / blocked path
                return []

            if best_succ in visited:
                # Cycle detected due to broken graph consistency
                return []

            path.append(best_succ)
            visited.add(best_succ)
            current = best_succ

        return path

    def get_path_cost(self, path: Optional[List[str]] = None) -> float:
        """
        Calculates the true total accumulated traversal cost of a route.

        Args:
            path: Optional list of node IDs. Defaults to current get_path().

        Returns:
            Cumulative cost as float, or math.inf if unreachable.
        """
        p = path if path is not None else self.get_path()
        if not p:
            return math.inf
        if len(p) == 1:
            return 0.0 if p[0] == self.goal_id else math.inf

        total_cost = 0.0
        for i in range(len(p) - 1):
            edge_cost = self.graph.get_edge_cost(p[i], p[i + 1])
            if math.isinf(edge_cost):
                return math.inf
            total_cost += edge_cost

        return total_cost

    def move_start(self, new_start_id: str) -> None:
        """
        Advances the vessel's current position to a new start waypoint.
        Updates the heuristic modifier km to preserve heuristic consistency.
        """
        if not self.graph.get_node(new_start_id):
            raise KeyError(f"Node '{new_start_id}' not found in graph.")

        self.km += self.heuristic(self.last_start_id, new_start_id)
        self.start_id = new_start_id
        self.last_start_id = new_start_id

    def update_edge(
        self,
        source_id: str,
        target_id: str,
        new_cost: Optional[float] = None,
    ) -> None:
        """
        Notifies D* Lite that a directed edge cost has changed.
        Updates only the affected source vertex in O(1) time without rebuilding the graph.

        Args:
            source_id: Origin waypoint ID.
            target_id: Destination waypoint ID.
            new_cost: Optional explicit cost override on the edge.
        """
        if new_cost is not None:
            edge = self.graph.get_edge(source_id, target_id)
            if edge:
                edge.cost = new_cost

        # In D* Lite (goal-directed backward search), changing c(u, v) modifies rhs(u)
        self.update_vertex(source_id)

    def update_node(self, node_id: str) -> None:
        """
        Notifies D* Lite that a waypoint's navigability has changed (e.g. marked an obstacle).
        Updates the node and all its incoming predecessors and outgoing successors.
        """
        self.update_vertex(node_id)
        for pred in self.graph.get_predecessors(node_id):
            self.update_vertex(pred.node_id)
        for succ in self.graph.get_successors(node_id):
            self.update_vertex(succ.node_id)

    def replan(self) -> List[str]:
        """
        Incrementally repairs the shortest path tree from the current start position and returns the updated route.
        """
        self.compute_shortest_path()
        return self.get_path()
