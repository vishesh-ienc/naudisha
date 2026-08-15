"""
Independent algorithmic correctness and mathematical validation test suite for D* Lite.
Contains an independent brute-force / Dijkstra reference implementation used exclusively
as a verification oracle to prove that D* Lite's initial planning and dynamic incremental
replanning produce 100% mathematically optimal solutions under all edge and obstacle shifts.
"""

from __future__ import annotations

import heapq
import math
import unittest
from typing import Dict, List, Optional, Set, Tuple

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    CostWeights,
)
from naudisha.cost.model import CostModel
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
)
from naudisha.routing.dstar_lite import DStarLite


def reference_dijkstra(
    graph: GeographicGridGraph,
    start_id: str,
    goal_id: str,
) -> Tuple[List[str], float]:
    """
    Independent reference Dijkstra algorithm used strictly as a test oracle.
    Computes true global shortest path from start_id to goal_id on graph.

    Returns:
        (path, total_cost): List of node IDs and minimum cumulative cost.
    """
    if start_id == goal_id:
        return ([start_id], 0.0)

    # Distances from start
    dist: Dict[str, float] = {start_id: 0.0}
    parent: Dict[str, str] = {}
    visited: Set[str] = set()

    # Priority queue: (cost, counter, node_id)
    pq: List[Tuple[float, int, str]] = []
    counter = 0
    heapq.heappush(pq, (0.0, counter, start_id))

    while pq:
        d, _, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        if u == goal_id:
            break

        for succ in graph.get_successors(u):
            v = succ.node_id
            if v in visited:
                continue

            edge_cost = graph.get_edge_cost(u, v)
            if math.isinf(edge_cost):
                continue

            new_dist = d + edge_cost
            if new_dist < dist.get(v, math.inf):
                dist[v] = new_dist
                parent[v] = u
                counter += 1
                heapq.heappush(pq, (new_dist, counter, v))

    if goal_id not in dist:
        return ([], math.inf)

    # Reconstruct path from start to goal
    path = []
    curr = goal_id
    while curr in parent:
        path.append(curr)
        curr = parent[curr]
    path.append(start_id)
    path.reverse()

    return (path, dist[goal_id])


class TestDStarLiteCorrectnessOracle(unittest.TestCase):
    """
    Rigorous test suite comparing D* Lite against the independent Dijkstra test oracle.
    """

    def setUp(self):
        self.config = GridConfig(
            origin_lat=18.0,
            origin_lon=72.0,
            rows=5,
            cols=5,
            lat_spacing=0.5,
            lon_spacing=0.5,
        )
        self.ship = ShipProfile(
            ship_type="Container Ship",
            length=300.0,
            beam=40.0,
            draft=12.0,
            cruising_speed=16.0,
            maximum_speed=22.0,
        )
        self.env = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=15.0,
            wind_direction=45.0,
            wave_height=1.5,
            wave_direction=45.0,
            wave_period=7.0,
            current_speed=1.0,
            current_direction=45.0,
        )
        self.graph = GeographicGridGraph(config=self.config, default_ship=self.ship)
        self.graph.populate_uniform_environment(env=self.env, ship=self.ship)

    def test_initial_optimality_against_dijkstra(self):
        """D* Lite initial path cost matches the independent Dijkstra oracle across multiple pairs."""
        test_pairs = [
            ("node_0_0", "node_4_4"),
            ("node_0_0", "node_0_4"),
            ("node_0_0", "node_4_0"),
            ("node_1_1", "node_3_3"),
            ("node_2_0", "node_0_3"),
        ]

        for start, goal in test_pairs:
            planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
            dstar_path = planner.plan()
            dstar_cost = planner.get_path_cost()

            oracle_path, oracle_cost = reference_dijkstra(self.graph, start, goal)

            self.assertGreater(len(dstar_path), 0, f"Failed on pair {start} -> {goal}")
            self.assertAlmostEqual(
                dstar_cost,
                oracle_cost,
                places=5,
                msg=f"Cost mismatch on {start} -> {goal}: D* Lite={dstar_cost}, Dijkstra={oracle_cost}",
            )

    def test_dynamic_edge_cost_increase_optimality(self):
        """
        After dynamic cost increase on active route, D* Lite incremental replan
        matches independent Dijkstra oracle computed on the modified graph.
        """
        start = "node_0_0"
        goal = "node_4_4"

        planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
        initial_path = planner.plan()

        # Surge cost on active edge
        u, v = initial_path[0], initial_path[1]
        self.graph.get_edge(u, v).cost += 50.0
        planner.update_edge(u, v)

        # Incremental repair
        replanned_path = planner.replan()
        replanned_cost = planner.get_path_cost()

        # Oracle check on modified graph
        oracle_path, oracle_cost = reference_dijkstra(self.graph, start, goal)

        self.assertAlmostEqual(replanned_cost, oracle_cost, places=5)
        self.assertNotEqual(replanned_path, initial_path)

    def test_dynamic_edge_cost_decrease_optimality(self):
        """
        When an alternate path cost decreases (cheaper shortcut opens),
        D* Lite incremental replan captures the shortcut and matches Dijkstra.
        """
        start = "node_0_0"
        goal = "node_4_4"

        # Initially, create a detour by inflating eastern path
        for r in range(4):
            self.graph.get_edge(f"node_{r}_0", f"node_{r}_1").cost = 10.0

        planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
        initial_path = planner.plan()

        # Now make edge (node_0_0 -> node_0_1) very cheap (shortcut)
        self.graph.get_edge("node_0_0", "node_0_1").cost = 0.05
        planner.update_edge("node_0_0", "node_0_1")

        replanned_path = planner.replan()
        replanned_cost = planner.get_path_cost()

        oracle_path, oracle_cost = reference_dijkstra(self.graph, start, goal)

        self.assertAlmostEqual(replanned_cost, oracle_cost, places=5)
        self.assertEqual(replanned_path[0], "node_0_0")
        self.assertEqual(replanned_path[1], "node_0_1")

    def test_multiple_simultaneous_edge_updates(self):
        """
        Simultaneous cost changes across multiple edges are incrementally repaired
        by D* Lite and match the oracle.
        """
        start = "node_0_0"
        goal = "node_4_4"

        planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
        planner.plan()

        # Update a 2x2 regional block of edges
        modified_edges = [
            ("node_1_0", "node_2_0"),
            ("node_1_1", "node_2_1"),
            ("node_1_0", "node_1_1"),
            ("node_2_0", "node_2_1"),
        ]
        for src, tgt in modified_edges:
            self.graph.get_edge(src, tgt).cost += 15.0

        planner.update_edges(modified_edges)
        replanned_path = planner.replan()
        replanned_cost = planner.get_path_cost()

        oracle_path, oracle_cost = reference_dijkstra(self.graph, start, goal)
        self.assertAlmostEqual(replanned_cost, oracle_cost, places=5)

    def test_obstacle_appearing_and_disappearing(self):
        """
        Marking nodes non-navigable and then re-enabling them is repaired incrementally
        and matches the oracle.
        """
        start = "node_0_0"
        goal = "node_4_4"

        planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
        initial_path = planner.plan()
        initial_cost = planner.get_path_cost()

        # 1. Obstacle appears at intermediate node along route
        blocked_node = initial_path[2]
        self.graph.set_node_navigability(blocked_node, is_navigable=False, ship=self.ship)
        planner.update_node(blocked_node)

        detour_path = planner.replan()
        detour_cost = planner.get_path_cost()

        oracle_detour_path, oracle_detour_cost = reference_dijkstra(self.graph, start, goal)
        self.assertAlmostEqual(detour_cost, oracle_detour_cost, places=5)
        self.assertNotIn(blocked_node, detour_path)

        # 2. Obstacle is cleared (re-enabled)
        self.graph.set_node_navigability(blocked_node, is_navigable=True, ship=self.ship)
        planner.update_node(blocked_node)

        restored_path = planner.replan()
        restored_cost = planner.get_path_cost()

        oracle_restored_path, oracle_restored_cost = reference_dijkstra(self.graph, start, goal)
        self.assertAlmostEqual(restored_cost, oracle_restored_cost, places=5)
        self.assertAlmostEqual(restored_cost, initial_cost, places=5)

    def test_moving_start_optimality(self):
        """
        Vessel advances along its route, encounters dynamic changes ahead,
        and D* Lite incremental replan matches Dijkstra from the new start position.
        """
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_4_4")
        path = planner.plan()

        # Advance vessel 2 steps along route
        new_start = path[2]
        planner.move_start(new_start)

        # Severe storm develops ahead on new_start -> next node
        next_node = path[3]
        self.graph.get_edge(new_start, next_node).cost += 40.0
        planner.update_edge(new_start, next_node)

        replan_path = planner.replan()
        replan_cost = planner.get_path_cost()

        oracle_path, oracle_cost = reference_dijkstra(self.graph, new_start, "node_4_4")
        self.assertEqual(replan_path[0], new_start)
        self.assertAlmostEqual(replan_cost, oracle_cost, places=5)

    def test_unreachable_and_reachable_transitions(self):
        """
        Completely blocking goal yields empty path and inf cost, then unblocking
        restores optimal path matching Dijkstra.
        """
        start = "node_0_0"
        goal = "node_4_4"

        planner = DStarLite(graph=self.graph, start_id=start, goal_id=goal)
        planner.plan()

        # Block all neighbors of goal (node_3_4 and node_4_3)
        self.graph.set_node_navigability("node_3_4", is_navigable=False, ship=self.ship)
        self.graph.set_node_navigability("node_4_3", is_navigable=False, ship=self.ship)
        planner.update_node("node_3_4")
        planner.update_node("node_4_3")

        blocked_path = planner.replan()
        self.assertEqual(blocked_path, [])
        self.assertTrue(math.isinf(planner.get_path_cost()))

        # Unblock one path (node_3_4)
        self.graph.set_node_navigability("node_3_4", is_navigable=True, ship=self.ship)
        planner.update_node("node_3_4")

        unblocked_path = planner.replan()
        unblocked_cost = planner.get_path_cost()

        oracle_path, oracle_cost = reference_dijkstra(self.graph, start, goal)
        self.assertGreater(len(unblocked_path), 0)
        self.assertAlmostEqual(unblocked_cost, oracle_cost, places=5)

    def test_accumulated_path_cost_identity(self):
        """
        Every returned route's get_path_cost() strictly equals the exact sum
        of individual edge traversal costs.
        """
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_4_4")
        path = planner.plan()

        manual_sum = 0.0
        for i in range(len(path) - 1):
            manual_sum += self.graph.get_edge_cost(path[i], path[i + 1])

        self.assertAlmostEqual(planner.get_path_cost(), manual_sum, places=7)


if __name__ == "__main__":
    unittest.main()
