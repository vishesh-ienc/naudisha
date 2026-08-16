"""
Offline unit tests for live environmental data integration into GeographicGridGraph.
Verifies provider dependency injection, edge midpoint spatial sampling, explicit timestamp handling,
cost recalculation, selective edge refreshing, error handling, and D* Lite route planning
using deterministic mock weather providers without network access.
"""

import math
import unittest
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Union

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    CostWeights,
)
from naudisha.cost.model import CostModel
from naudisha.data.weather_provider import WeatherProvider
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
    GridEnvironmentUpdateError,
)
from naudisha.routing.dstar_lite import DStarLite


class RecordingMockProvider(WeatherProvider):
    """
    Mock WeatherProvider that records all coordinate and timestamp query parameters,
    and returns spatially varying environmental conditions.
    """

    def __init__(self, failure_coords: Tuple[float, float] = None) -> None:
        self.queries: List[Tuple[float, float, str]] = []
        self.failure_coords = failure_coords

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        time_str = timestamp if isinstance(timestamp, str) else timestamp.isoformat()
        self.queries.append((lat, lon, time_str))

        if self.failure_coords is not None:
            if math.isclose(lat, self.failure_coords[0], abs_tol=1e-3) and math.isclose(
                lon, self.failure_coords[1], abs_tol=1e-3
            ):
                raise RuntimeError(f"Simulated network/sensor outage at ({lat:.4f}, {lon:.4f})")

        # Spatially distinct conditions based on coordinates
        return EnvironmentalData(
            timestamp=time_str,
            wind_speed=10.0 + (lat - 18.0) * 5.0,
            wind_direction=270.0,
            wave_height=1.0 + (lon - 72.0) * 1.0,
            wave_direction=250.0,
            wave_period=8.0,
            current_speed=0.5 + (lat - 18.0) * 0.2,
            current_direction=90.0,
        )


class TestGridEnvironmentIntegration(unittest.TestCase):
    """Test suite for GeographicGridGraph environmental data integration."""

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
            ship_type="Test Panamax",
            length=250.0,
            beam=32.0,
            draft=10.0,
            cruising_speed=18.0,
            maximum_speed=22.0,
        )
        self.timestamp = "2026-08-16T12:00:00Z"

    def test_graph_accepts_injected_provider(self):
        """1. Graph accepts injected WeatherProvider via constructor."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )
        self.assertIs(graph.environment_provider, provider)

    def test_populate_environment_midpoint_coordinates_and_timestamp(self):
        """2-5. populate_environment() queries provider at exact edge midpoints with explicit timestamp."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )

        graph.populate_environment(timestamp=self.timestamp)

        # 3x3 grid has 24 directed edges
        self.assertEqual(len(provider.queries), 24)

        # Verify midpoint sampling for edge node_0_0 (18.0, 72.0) -> node_1_0 (18.5, 72.0)
        # Midpoint = (18.25, 72.0)
        midpoint_00_10 = graph.get_edge_midpoint("node_0_0", "node_1_0")
        self.assertAlmostEqual(midpoint_00_10[0], 18.25)
        self.assertAlmostEqual(midpoint_00_10[1], 72.00)

        # Midpoint for edge node_0_0 (18.0, 72.0) -> node_0_1 (18.0, 72.5)
        # Midpoint = (18.0, 72.25)
        midpoint_00_01 = graph.get_edge_midpoint("node_0_0", "node_0_1")
        self.assertAlmostEqual(midpoint_00_01[0], 18.00)
        self.assertAlmostEqual(midpoint_00_01[1], 72.25)

        # Check all queries passed the exact timestamp
        for lat, lon, q_time in provider.queries:
            self.assertEqual(q_time, self.timestamp)

    def test_edge_cost_recalculated_using_cost_model(self):
        """6-8. Returned EnvironmentalData is stored on edge and cost is calculated via CostModel."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )

        # Before population, edge cost is math.inf (uninitialized)
        self.assertEqual(graph.get_edge_cost("node_0_0", "node_1_0"), math.inf)

        graph.populate_environment(timestamp=self.timestamp)

        # After population, edge cost is finite and evaluation is attached
        edge = graph.get_edge("node_0_0", "node_1_0")
        self.assertIsNotNone(edge.env_data)
        self.assertTrue(math.isfinite(edge.cost))
        self.assertIsNotNone(edge.evaluation)
        self.assertAlmostEqual(edge.cost, edge.evaluation.total_cost)

        # Opposing edge node_1_0 -> node_0_0 receives same midpoint weather but different current bearing
        # (resulting in directional asymmetry in along-track current)
        rev_edge = graph.get_edge("node_1_0", "node_0_0")
        self.assertIsNotNone(rev_edge.env_data)
        self.assertTrue(math.isfinite(rev_edge.cost))
        self.assertNotEqual(edge.cost, rev_edge.cost)

    def test_selective_refresh_edges(self):
        """9-10. refresh_edges() updates only requested edges; unrelated edges remain untouched."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )

        graph.populate_environment(timestamp=self.timestamp)
        initial_cost_00_10 = graph.get_edge_cost("node_0_0", "node_1_0")
        initial_cost_10_20 = graph.get_edge_cost("node_1_0", "node_2_0")
        initial_queries_count = len(provider.queries)

        # Create a custom provider with higher wind
        new_timestamp = "2026-08-16T18:00:00Z"
        class StormyProvider(WeatherProvider):
            def fetch_conditions(self, lat, lon, timestamp):
                return EnvironmentalData(
                    timestamp=timestamp,
                    wind_speed=35.0,  # Severe gale
                    wind_direction=0.0,
                    wave_height=4.5,
                    wave_direction=0.0,
                    wave_period=10.0,
                    current_speed=2.0,
                    current_direction=180.0,
                )

        storm_provider = StormyProvider()
        graph.refresh_edges(
            edges=[("node_0_0", "node_1_0")],
            timestamp=new_timestamp,
            provider=storm_provider,
        )

        # Only 1 edge should have changed
        refreshed_cost_00_10 = graph.get_edge_cost("node_0_0", "node_1_0")
        unrelated_cost_10_20 = graph.get_edge_cost("node_1_0", "node_2_0")

        self.assertNotEqual(refreshed_cost_00_10, initial_cost_00_10)
        self.assertEqual(unrelated_cost_10_20, initial_cost_10_20)
        self.assertEqual(graph.get_edge("node_0_0", "node_1_0").env_data.timestamp, new_timestamp)

    def test_provider_failure_raises_grid_environment_update_error(self):
        """11. Provider failure raises GridEnvironmentUpdateError with rich edge/coordinate context."""
        # Fail at midpoint (18.25, 72.0)
        failing_provider = RecordingMockProvider(failure_coords=(18.25, 72.0))
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=failing_provider,
        )

        with self.assertRaises(GridEnvironmentUpdateError) as ctx:
            graph.populate_environment(timestamp=self.timestamp)

        err_msg = str(ctx.exception)
        self.assertIn("node_0_0", err_msg)
        self.assertIn("node_1_0", err_msg)
        self.assertIn("18.2500N", err_msg)
        self.assertIn("72.0000E", err_msg)

    def test_non_navigable_edges_not_queried(self):
        """12. Non-navigable obstacle nodes disable incident edges and avoid querying provider."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )

        # Mark center node (1, 1) as non-navigable obstacle
        graph.set_node_navigability("node_1_1", False)

        graph.populate_environment(timestamp=self.timestamp)

        # In 3x3 grid, center node has 4 incoming and 4 outgoing edges (total 8 incident edges)
        # 24 total edges - 8 incident non-navigable edges = 16 queries
        self.assertEqual(len(provider.queries), 16)
        self.assertEqual(graph.get_edge_cost("node_0_1", "node_1_1"), math.inf)
        self.assertEqual(graph.get_edge_cost("node_1_1", "node_2_1"), math.inf)

    def test_dstar_lite_seamless_routing_on_populated_grid(self):
        """14. D* Lite plans optimal routes seamlessly on the environment-populated grid."""
        provider = RecordingMockProvider()
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=provider,
        )

        graph.populate_environment(timestamp=self.timestamp)

        # Initialize D* Lite
        dstar = DStarLite(graph=graph, start_id="node_0_0", goal_id="node_2_2")
        dstar.compute_shortest_path()
        route = dstar.get_path()

        self.assertGreater(len(route), 0)
        self.assertEqual(route[0], "node_0_0")
        self.assertEqual(route[-1], "node_2_2")

        initial_cost = dstar.get_path_cost()
        self.assertTrue(math.isfinite(initial_cost))

        # Dynamic weather shift on active edge
        first_step = (route[0], route[1])
        graph.update_edge_environment(
            first_step[0],
            first_step[1],
            EnvironmentalData(
                timestamp=self.timestamp,
                wind_speed=55.0,  # Exceeds max operational limit -> non-navigable
                wind_direction=0.0,
                wave_height=9.0,
                wave_direction=0.0,
                wave_period=14.0,
                current_speed=3.0,
                current_direction=180.0,
            ),
        )

        # Notify D* Lite and replan
        dstar.update_edge(first_step[0], first_step[1])
        dstar.compute_shortest_path()
        new_route = dstar.get_path()

        # D* Lite should successfully reroute around the stormy segment
        self.assertNotEqual(new_route, route)
        self.assertTrue(math.isfinite(dstar.get_path_cost()))

    def test_unconfigured_provider_raises_value_error(self):
        """15. Calling populate_environment without any provider configured raises ValueError."""
        graph = GeographicGridGraph(
            config=self.config,
            default_ship=self.ship,
            environment_provider=None,
        )

        with self.assertRaises(ValueError):
            graph.populate_environment(timestamp=self.timestamp)


if __name__ == "__main__":
    unittest.main()
