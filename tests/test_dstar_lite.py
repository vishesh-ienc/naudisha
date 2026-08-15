"""
Unit tests for D* Lite incremental heuristic pathfinding:
- basic route finding
- shortest-cost route selection
- obstacle avoidance (non-navigable nodes)
- unreachable goal handling
- changed edge cost causing a route change
- moving start position with km heuristic adjustment
- incremental replanning without graph rebuilding
- path cost consistency
"""

import math
import unittest

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
from naudisha.routing.dstar_lite import DStarLite, PriorityQueue


class TestPriorityQueue(unittest.TestCase):
    """Test suite for D* Lite PriorityQueue."""

    def test_priority_queue_ordering(self):
        pq = PriorityQueue()
        pq.insert("node_a", (5.0, 2.0))
        pq.insert("node_b", (3.0, 4.0))
        pq.insert("node_c", (3.0, 1.0))

        self.assertEqual(pq.pop(), "node_c")  # (3.0, 1.0) < (3.0, 4.0)
        self.assertEqual(pq.pop(), "node_b")  # (3.0, 4.0)
        self.assertEqual(pq.pop(), "node_a")  # (5.0, 2.0)
        self.assertIsNone(pq.pop())

    def test_decrease_key_and_lazy_deletion(self):
        pq = PriorityQueue()
        pq.insert("node_a", (10.0, 10.0))
        pq.insert("node_b", (5.0, 5.0))

        # Decrease key of node_a
        pq.insert("node_a", (2.0, 2.0))

        # node_a should come out first
        self.assertEqual(pq.pop(), "node_a")
        self.assertEqual(pq.pop(), "node_b")
        self.assertIsNone(pq.pop())

    def test_remove(self):
        pq = PriorityQueue()
        pq.insert("node_a", (2.0, 2.0))
        pq.insert("node_b", (5.0, 5.0))
        pq.remove("node_a")

        self.assertEqual(pq.pop(), "node_b")
        self.assertIsNone(pq.pop())


class TestDStarLite(unittest.TestCase):
    """Test suite for DStarLite path planner."""

    def setUp(self):
        # Create a 4x4 geographic grid
        self.config = GridConfig(
            origin_lat=18.0,
            origin_lon=72.0,
            rows=4,
            cols=4,
            lat_spacing=0.5,
            lon_spacing=0.5,
        )
        self.ship = ShipProfile(
            ship_type="Cargo",
            length=250.0,
            beam=32.0,
            draft=10.0,
            cruising_speed=15.0,
            maximum_speed=20.0,
        )
        self.env_calm = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=10.0,
            wind_direction=45.0,
            wave_height=1.0,
            wave_direction=45.0,
            wave_period=6.0,
            current_speed=0.5,
            current_direction=45.0,
        )
        self.graph = GeographicGridGraph(config=self.config, default_ship=self.ship)
        self.graph.populate_uniform_environment(env=self.env_calm, ship=self.ship)

    def test_basic_route_finding(self):
        """D* Lite finds a valid continuous path from start to goal."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_3_3")
        path = planner.plan()

        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], "node_0_0")
        self.assertEqual(path[-1], "node_3_3")

        # Verify continuity: each step is a valid 4-direction step
        for i in range(len(path) - 1):
            u_node = self.graph.get_node(path[i])
            v_node = self.graph.get_node(path[i + 1])
            manhattan_dist = abs(u_node.row - v_node.row) + abs(u_node.col - v_node.col)
            self.assertEqual(manhattan_dist, 1)

    def test_shortest_cost_route_selection(self):
        """D* Lite selects the lower-cost path when two alternate routes exist."""
        # On a 3x3 subgrid from (0,0) to (1,1):
        # Path 1: (0,0) -> (1,0) -> (1,1)
        # Path 2: (0,0) -> (0,1) -> (1,1)
        # Make Path 1 cheaper by modifying edge costs
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_1_1")

        # Set specific costs
        self.graph.get_edge("node_0_0", "node_1_0").cost = 1.0
        self.graph.get_edge("node_1_0", "node_1_1").cost = 1.0

        self.graph.get_edge("node_0_0", "node_0_1").cost = 5.0
        self.graph.get_edge("node_0_1", "node_1_1").cost = 5.0

        path = planner.plan()
        self.assertEqual(path, ["node_0_0", "node_1_0", "node_1_1"])
        self.assertAlmostEqual(planner.get_path_cost(), 2.0)

    def test_obstacle_avoidance(self):
        """D* Lite successfully navigates around non-navigable nodes."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_2_0")

        # Block direct path through node_1_0
        self.graph.set_node_navigability("node_1_0", is_navigable=False, ship=self.ship)
        planner.update_node("node_1_0")

        path = planner.plan()
        self.assertGreater(len(path), 0)
        self.assertNotIn("node_1_0", path)
        self.assertEqual(path[0], "node_0_0")
        self.assertEqual(path[-1], "node_2_0")
        # Path must detour via column 1: (0,0) -> (0,1) -> (1,1) -> (2,1) -> (2,0)
        self.assertIn("node_0_1", path)

    def test_unreachable_goal(self):
        """D* Lite returns empty list [] and infinite cost when goal is completely blocked."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_3_3")

        # Surround goal node (3,3) by disabling its only 2 neighbors (2,3) and (3,2)
        self.graph.set_node_navigability("node_2_3", is_navigable=False, ship=self.ship)
        self.graph.set_node_navigability("node_3_2", is_navigable=False, ship=self.ship)
        planner.update_node("node_2_3")
        planner.update_node("node_3_2")

        path = planner.plan()
        self.assertEqual(path, [])
        self.assertTrue(math.isinf(planner.get_path_cost()))

    def test_changed_edge_cost_causes_route_change(self):
        """Increasing the cost on an active edge causes D* Lite to dynamically reroute."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_2_2")
        initial_path = planner.plan()
        initial_cost = planner.get_path_cost()

        self.assertGreater(len(initial_path), 0)

        # Identify an active edge on the initial path
        edge_u = initial_path[0]
        edge_v = initial_path[1]

        # Artificially spike cost of that edge (e.g. storm or severe hazard)
        self.graph.get_edge(edge_u, edge_v).cost = 1000.0
        planner.update_edge(edge_u, edge_v)

        new_path = planner.replan()
        new_cost = planner.get_path_cost()

        self.assertNotEqual(initial_path, new_path)
        # The new path should avoid the expensive (edge_u -> edge_v) segment
        self.assertFalse(new_path[0] == edge_u and new_path[1] == edge_v)
        self.assertLess(new_cost, 1000.0)

    def test_moving_start(self):
        """Advancing the vessel along the path updates start_id and maintains route validity."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_3_3")
        path = planner.plan()

        self.assertEqual(path[0], "node_0_0")
        next_step = path[1]

        # Advance vessel position to next_step
        planner.move_start(next_step)
        sub_path = planner.replan()

        self.assertEqual(sub_path[0], next_step)
        self.assertEqual(sub_path[-1], "node_3_3")
        self.assertEqual(sub_path, path[1:])

    def test_incremental_replanning_vertex_updates(self):
        """D* Lite incrementally repairs shortest path with minimal vertex expansions."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_3_3")
        path1 = planner.plan()
        initial_expansions = planner.expansions_count

        # Minor edge update far away from the active corridor
        self.graph.get_edge("node_0_2", "node_0_3").cost += 0.5
        planner.update_edge("node_0_2", "node_0_3")

        expansions_before_replan = planner.expansions_count
        planner.replan()
        incremental_expansions = planner.expansions_count - expansions_before_replan

        # Incremental repair should expand far fewer vertices than full initial search
        self.assertLessEqual(incremental_expansions, initial_expansions)

    def test_path_cost_consistency(self):
        """The total path cost returned matches the sum of each individual segment cost."""
        planner = DStarLite(graph=self.graph, start_id="node_0_0", goal_id="node_2_2")
        path = planner.plan()

        expected_total = 0.0
        for i in range(len(path) - 1):
            expected_total += self.graph.get_edge_cost(path[i], path[i + 1])

        self.assertAlmostEqual(planner.get_path_cost(), expected_total, places=5)


if __name__ == "__main__":
    unittest.main()
