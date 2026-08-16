"""
Unit tests for GeographicGridGraph and routing environment layer:
- grid creation and configuration validation
- node coordinates accuracy
- 4-direction neighbor generation (corner, edge, interior)
- directed edge creation
- node and edge navigability constraints
- edge cost calculation through CostModel
- updating environmental data on a specific edge
- changed environmental data producing a changed edge cost
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
    GridNode,
    GridEdge,
    GeographicGridGraph,
)


class TestGeographicGridGraph(unittest.TestCase):
    """Test suite for GeographicGridGraph."""

    def setUp(self):
        self.config = GridConfig(
            origin_lat=18.0,
            origin_lon=72.0,
            rows=3,
            cols=3,
            lat_spacing=0.5,
            lon_spacing=0.5,
        )
        self.ship = ShipProfile(
            ship_type="Container",
            length=300.0,
            beam=40.0,
            draft=12.0,
            cruising_speed=16.0,
            maximum_speed=22.0,
        )
        self.env_calm = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=10.0,
            wind_direction=0.0,
            wave_height=1.0,
            wave_direction=0.0,
            wave_period=6.0,
            current_speed=1.0,
            current_direction=0.0,
        )
        self.graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
        )

    def test_grid_config_validation(self):
        """GridConfig validates positive dimensions and valid coordinate bounds."""
        with self.assertRaises(ValueError):
            GridConfig(origin_lat=18.0, origin_lon=72.0, rows=0, cols=3, lat_spacing=0.5, lon_spacing=0.5)
        with self.assertRaises(ValueError):
            GridConfig(origin_lat=18.0, origin_lon=72.0, rows=3, cols=3, lat_spacing=-0.5, lon_spacing=0.5)
        with self.assertRaises(ValueError):
            GridConfig(origin_lat=95.0, origin_lon=72.0, rows=3, cols=3, lat_spacing=0.5, lon_spacing=0.5)

    def test_grid_creation_and_node_count(self):
        """3x3 grid creates exactly 9 nodes."""
        nodes = self.graph.get_all_nodes()
        self.assertEqual(len(nodes), 9)

    def test_node_coordinates(self):
        """Node coordinates correctly reflect origin and spacing offsets."""
        # Origin node (0, 0)
        n00 = self.graph.get_node("node_0_0")
        self.assertIsNotNone(n00)
        self.assertAlmostEqual(n00.lat, 18.0)
        self.assertAlmostEqual(n00.lon, 72.0)

        # Coordinate lookup
        n12 = self.graph.get_node_by_coords(row=1, col=2)
        self.assertIsNotNone(n12)
        self.assertAlmostEqual(n12.lat, 18.5)
        self.assertAlmostEqual(n12.lon, 73.0)

        # Top-right node (2, 2)
        n22 = self.graph.get_node("node_2_2")
        self.assertIsNotNone(n22)
        self.assertAlmostEqual(n22.lat, 19.0)
        self.assertAlmostEqual(n22.lon, 73.0)

    def test_neighbor_generation_4_directions(self):
        """4-direction neighbors accurately count corner, edge, and interior neighbors."""
        # Corner node (0, 0) has 2 neighbors: North (1, 0) and East (0, 1)
        neighbors_00 = self.graph.get_neighbors("node_0_0")
        neighbor_ids_00 = {n.node_id for n in neighbors_00}
        self.assertEqual(len(neighbor_ids_00), 2)
        self.assertEqual(neighbor_ids_00, {"node_1_0", "node_0_1"})

        # Edge node (0, 1) has 3 neighbors: West (0, 0), East (0, 2), North (1, 1)
        neighbors_01 = self.graph.get_neighbors("node_0_1")
        neighbor_ids_01 = {n.node_id for n in neighbors_01}
        self.assertEqual(len(neighbor_ids_01), 3)
        self.assertEqual(neighbor_ids_01, {"node_0_0", "node_0_2", "node_1_1"})

        # Interior node (1, 1) has 4 neighbors: North (2, 1), South (0, 1), East (1, 2), West (1, 0)
        neighbors_11 = self.graph.get_neighbors("node_1_1")
        neighbor_ids_11 = {n.node_id for n in neighbors_11}
        self.assertEqual(len(neighbor_ids_11), 4)
        self.assertEqual(neighbor_ids_11, {"node_2_1", "node_0_1", "node_1_2", "node_1_0"})

    def test_predecessors_and_successors(self):
        """Predecessors and successors match directed connectivity."""
        successors_00 = {n.node_id for n in self.graph.get_successors("node_0_0")}
        predecessors_00 = {n.node_id for n in self.graph.get_predecessors("node_0_0")}
        self.assertEqual(successors_00, {"node_1_0", "node_0_1"})
        self.assertEqual(predecessors_00, {"node_1_0", "node_0_1"})

    def test_edge_creation_count(self):
        """A 3x3 grid with 4-direction directed connectivity has 2 * (3*2 + 3*2) = 24 directed edges."""
        edges = self.graph.get_all_edges()
        self.assertEqual(len(edges), 24)

    def test_edge_cost_calculation_through_cost_model(self):
        """Edge cost is computed via CostModel when environmental data is assigned."""
        # Before assigning environment, cost is math.inf
        self.assertTrue(math.isinf(self.graph.get_edge_cost("node_0_0", "node_1_0")))

        # Assign uniform environment
        self.graph.populate_uniform_environment(env=self.env_calm, ship=self.ship)

        # After assigning, cost should be finite and positive
        cost = self.graph.get_edge_cost("node_0_0", "node_1_0")
        self.assertFalse(math.isinf(cost))
        self.assertGreater(cost, 0.0)

        edge = self.graph.get_edge("node_0_0", "node_1_0")
        self.assertIsNotNone(edge.evaluation)
        self.assertEqual(edge.cost, cost)

    def test_updating_environmental_data_changes_cost(self):
        """Updating environmental conditions on a specific edge changes its cost without rebuilding."""
        self.graph.populate_uniform_environment(env=self.env_calm, ship=self.ship)
        initial_cost = self.graph.get_edge_cost("node_0_0", "node_1_0")

        # Inject severe headwind & high waves on edge (node_0_0 -> node_1_0)
        # Node (0, 0) -> (1, 0) is navigating North (0° bearing)
        storm_env = EnvironmentalData(
            timestamp="2026-08-16T15:00:00Z",
            wind_speed=45.0,        # Severe 45 kt wind
            wind_direction=0.0,     # From North (direct headwind)
            wave_height=6.0,        # 6m high waves
            wave_direction=0.0,     # Head seas
            wave_period=10.0,
            current_speed=3.0,
            current_direction=180.0,# Flowing South (direct opposing current)
        )

        updated_cost = self.graph.update_edge_environment(
            source_id="node_0_0",
            target_id="node_1_0",
            env=storm_env,
            ship=self.ship,
        )

        self.assertGreater(updated_cost, initial_cost)
        self.assertEqual(self.graph.get_edge_cost("node_0_0", "node_1_0"), updated_cost)

        # Ensure other untouched edges (e.g. node_0_0 -> node_0_1) still have initial calm cost
        other_cost = self.graph.get_edge_cost("node_0_0", "node_0_1")
        self.assertFalse(math.isinf(other_cost))
        self.assertNotEqual(other_cost, updated_cost)

    def test_navigability_and_obstacles(self):
        """Marking a node non-navigable updates incident edge costs to math.inf."""
        self.graph.populate_uniform_environment(env=self.env_calm, ship=self.ship)

        # Verify initial navigability
        self.assertTrue(self.graph.is_node_navigable("node_1_1"))
        self.assertTrue(self.graph.is_edge_navigable("node_0_1", "node_1_1"))
        self.assertTrue(self.graph.is_edge_navigable("node_1_1", "node_2_1"))

        # Mark node (1, 1) as non-navigable (e.g. island / shallow reef)
        self.graph.set_node_navigability("node_1_1", is_navigable=False, ship=self.ship)

        self.assertFalse(self.graph.is_node_navigable("node_1_1"))
        self.assertFalse(self.graph.is_edge_navigable("node_0_1", "node_1_1"))
        self.assertFalse(self.graph.is_edge_navigable("node_1_1", "node_2_1"))

        # All incoming and outgoing edges to node_1_1 must now have infinite cost
        self.assertTrue(math.isinf(self.graph.get_edge_cost("node_0_1", "node_1_1")))
        self.assertTrue(math.isinf(self.graph.get_edge_cost("node_1_1", "node_2_1")))
        self.assertTrue(math.isinf(self.graph.get_edge_cost("node_1_0", "node_1_1")))
        self.assertTrue(math.isinf(self.graph.get_edge_cost("node_1_1", "node_1_2")))

        # Other unrelated edges remain navigable with finite costs
        self.assertTrue(self.graph.is_edge_navigable("node_0_0", "node_1_0"))
        self.assertFalse(math.isinf(self.graph.get_edge_cost("node_0_0", "node_1_0")))


if __name__ == "__main__":
    unittest.main()
