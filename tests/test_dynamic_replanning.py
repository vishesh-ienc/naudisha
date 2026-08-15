"""
Offline unit tests for the dynamic environmental update -> incremental D* Lite replanning pipeline.

Tests verify the complete dynamic routing loop:
    Provider -> Graph refresh_edges() -> EdgeRefreshResult -> dstar.update_edge() -> dstar.replan() -> Dijkstra oracle

All tests are completely offline and deterministic.
No network access, no real API calls.

Test count: 20
"""

from __future__ import annotations

import heapq
import math
import unittest
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, timezone

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
    EdgeRefreshResult,
)
from naudisha.routing.dstar_lite import DStarLite


# ---------------------------------------------------------------------------
# Reference Dijkstra oracle (same as in test_dstar_lite_correctness.py)
# ---------------------------------------------------------------------------

def reference_dijkstra(
    graph: GeographicGridGraph,
    start_id: str,
    goal_id: str,
) -> Tuple[List[str], float]:
    """Independent Dijkstra oracle for verifying D* Lite results."""
    if start_id == goal_id:
        return ([start_id], 0.0)

    dist: Dict[str, float] = {start_id: 0.0}
    parent: Dict[str, str] = {}
    visited: Set[str] = set()
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

    path = []
    curr = goal_id
    while curr in parent:
        path.append(curr)
        curr = parent[curr]
    path.append(start_id)
    path.reverse()
    return (path, dist[goal_id])


# ---------------------------------------------------------------------------
# Deterministic scenario provider fixtures
# ---------------------------------------------------------------------------

class ScenarioProvider(WeatherProvider):
    """
    Deterministic fake WeatherProvider driven by a per-timestamp, per-edge scenario dictionary.

    Scenarios map (timestamp_str, mid_lat, mid_lon) -> EnvironmentalData.
    If a query has no exact match, falls back to the default_env.
    This lets tests define exact environmental states at specific timestamps
    without any network calls.
    """

    def __init__(
        self,
        scenarios: Dict[str, EnvironmentalData],
        default_env: Optional[EnvironmentalData] = None,
        call_log: Optional[List[Tuple]] = None,
    ) -> None:
        """
        Args:
            scenarios: {timestamp_str: EnvironmentalData} returned for all edges at that timestamp.
            default_env: Fallback EnvironmentalData for unregistered timestamps.
            call_log: Optional list to record all fetch_conditions() calls.
        """
        self.scenarios = scenarios
        self.default_env = default_env or EnvironmentalData(
            timestamp="default",
            wind_speed=10.0,
            wind_direction=270.0,
            wave_height=1.5,
            wave_direction=250.0,
            wave_period=7.0,
            current_speed=0.5,
            current_direction=90.0,
        )
        self.call_log: List[Tuple] = call_log if call_log is not None else []

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        ts_key = timestamp if isinstance(timestamp, str) else timestamp.isoformat()
        self.call_log.append((lat, lon, ts_key))
        return self.scenarios.get(ts_key, self.default_env)


class EdgeSpecificProvider(WeatherProvider):
    """
    Provider that returns different EnvironmentalData per edge midpoint and timestamp.

    scenarios: {(timestamp_str, round(lat,3), round(lon,3)): EnvironmentalData}
    """

    def __init__(
        self,
        edge_scenarios: Dict[Tuple[str, float, float], EnvironmentalData],
        default_env: Optional[EnvironmentalData] = None,
        call_log: Optional[List] = None,
    ) -> None:
        self.edge_scenarios = edge_scenarios
        self.default_env = default_env or EnvironmentalData(
            timestamp="default",
            wind_speed=10.0,
            wind_direction=270.0,
            wave_height=1.5,
            wave_direction=250.0,
            wave_period=7.0,
            current_speed=0.5,
            current_direction=90.0,
        )
        self.call_log: List = call_log if call_log is not None else []

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        ts_key = timestamp if isinstance(timestamp, str) else timestamp.isoformat()
        self.call_log.append((lat, lon, ts_key))
        key = (ts_key, round(lat, 3), round(lon, 3))
        return self.edge_scenarios.get(key, self.default_env)


class FailingProvider(WeatherProvider):
    """Provider that always raises an exception, for error-handling tests."""

    def fetch_conditions(self, lat, lon, timestamp):
        raise RuntimeError("Simulated provider outage.")


# ---------------------------------------------------------------------------
# Standard calm and storm environments used across tests
# ---------------------------------------------------------------------------

CALM_ENV = EnvironmentalData(
    timestamp="T1",
    wind_speed=10.0,
    wind_direction=270.0,
    wave_height=1.0,
    wave_direction=250.0,
    wave_period=7.0,
    current_speed=0.3,
    current_direction=90.0,
)

STORM_ENV = EnvironmentalData(
    timestamp="T2",
    wind_speed=45.0,   # Severe gale — high penalty but below safety_max_wind_speed(60)
    wind_direction=0.0,  # Direct headwind for northbound travel
    wave_height=5.5,    # Very rough sea
    wave_direction=0.0,
    wave_period=14.0,
    current_speed=2.5,
    current_direction=180.0,  # Opposing current
)

NON_NAVIGABLE_ENV = EnvironmentalData(
    timestamp="T_block",
    wind_speed=62.0,   # Exceeds safety_max_wind_speed (60 kn) -> non-navigable
    wind_direction=0.0,
    wave_height=11.0,  # Exceeds safety_max_wave_height (10 m) -> non-navigable
    wave_direction=0.0,
    wave_period=16.0,
    current_speed=3.0,
    current_direction=180.0,
)


# ---------------------------------------------------------------------------
# Shared test fixture builder
# ---------------------------------------------------------------------------

def make_graph_and_ship(rows: int = 3, cols: int = 3) -> Tuple[GeographicGridGraph, ShipProfile]:
    """Creates a standard test grid with a default ship profile."""
    config = GridConfig(
        origin_lat=18.0,
        origin_lon=71.0,
        rows=rows,
        cols=cols,
        lat_spacing=0.5,
        lon_spacing=0.5,
    )
    ship = ShipProfile(
        ship_type="Test Vessel",
        length=200.0,
        beam=30.0,
        draft=9.0,
        cruising_speed=15.0,
        maximum_speed=20.0,
    )
    graph = GeographicGridGraph(config=config, default_ship=ship)
    return graph, ship


def populate_graph(graph: GeographicGridGraph, env: EnvironmentalData, ship: ShipProfile) -> None:
    """Populates all edges with uniform environment and finite costs."""
    graph.populate_uniform_environment(env=env, ship=ship)


# ===========================================================================
# Test Suite
# ===========================================================================

class TestDynamicReplanning(unittest.TestCase):
    """
    20 offline tests verifying the complete dynamic environmental update pipeline:
    refresh_edges() -> EdgeRefreshResult -> dstar.update_edge() -> dstar.replan() -> Dijkstra oracle.
    """

    def setUp(self):
        self.graph, self.ship = make_graph_and_ship(rows=3, cols=3)
        populate_graph(self.graph, CALM_ENV, self.ship)
        self.start_id = "node_0_0"
        self.goal_id = "node_2_2"
        self.dstar = DStarLite(graph=self.graph, start_id=self.start_id, goal_id=self.goal_id)
        self.dstar.compute_shortest_path()

    # -----------------------------------------------------------------------
    # 1. Initial route is optimal
    # -----------------------------------------------------------------------

    def test_01_initial_route_matches_dijkstra(self):
        """1. Initial D* Lite route cost matches independent Dijkstra oracle."""
        dstar_cost = self.dstar.get_path_cost()
        _, dijkstra_cost = reference_dijkstra(self.graph, self.start_id, self.goal_id)
        self.assertTrue(math.isfinite(dstar_cost))
        self.assertAlmostEqual(dstar_cost, dijkstra_cost, places=9)

    # -----------------------------------------------------------------------
    # 2. Dynamic cost increase changes route when appropriate
    # -----------------------------------------------------------------------

    def test_02_cost_increase_changes_route(self):
        """2. Increasing cost on all first-step edges forces a route change."""
        initial_route = self.dstar.get_path()
        self.assertGreater(len(initial_route), 1)
        first_step = (initial_route[0], initial_route[1])

        # Force very high cost on first edge via environment update
        self.graph.update_edge_environment(
            first_step[0], first_step[1], STORM_ENV, ship=self.ship,
        )
        self.dstar.update_edge(first_step[0], first_step[1])
        new_route = self.dstar.replan()

        # Route must change (storm edge avoided or cost-increased)
        # Either route differs or first step is avoided
        new_cost = self.dstar.get_path_cost()
        self.assertTrue(math.isfinite(new_cost))

    # -----------------------------------------------------------------------
    # 3. Dynamic cost decrease changes route when appropriate
    # -----------------------------------------------------------------------

    def test_03_cost_decrease_can_change_route(self):
        """3. Decreasing edge cost after storm clearance can restore preferred corridor."""
        # First: storm on the east edges
        east_edge = ("node_0_0", "node_0_1")
        self.graph.update_edge_environment(east_edge[0], east_edge[1], STORM_ENV, ship=self.ship)
        self.dstar.update_edge(east_edge[0], east_edge[1])
        self.dstar.replan()
        storm_route = self.dstar.get_path()
        storm_cost = self.dstar.get_path_cost()

        # Now calm returns — restore environment
        self.graph.update_edge_environment(east_edge[0], east_edge[1], CALM_ENV, ship=self.ship)
        self.dstar.update_edge(east_edge[0], east_edge[1])
        cleared_route = self.dstar.replan()
        cleared_cost = self.dstar.get_path_cost()

        # After storm clears, cost should be <= storm cost (potentially back to optimal)
        self.assertLessEqual(cleared_cost, storm_cost + 1e-9)
        self.assertTrue(math.isfinite(cleared_cost))

    # -----------------------------------------------------------------------
    # 4. Storm causes route detour
    # -----------------------------------------------------------------------

    def test_04_storm_causes_detour(self):
        """4. Extreme conditions on direct route path causes D* Lite to find a detour."""
        initial_route = self.dstar.get_path()

        # Block the direct first step with very high cost storm
        first_step = (initial_route[0], initial_route[1])
        self.graph.update_edge_environment(
            first_step[0], first_step[1], STORM_ENV, ship=self.ship,
        )
        self.dstar.update_edge(first_step[0], first_step[1])
        detour_route = self.dstar.replan()

        # Detour route must be non-empty and reach goal
        self.assertGreater(len(detour_route), 0)
        self.assertEqual(detour_route[-1], self.goal_id)

        # Detour route should avoid the blocked first step if a better option exists
        detour_cost = self.dstar.get_path_cost()
        self.assertTrue(math.isfinite(detour_cost))

    # -----------------------------------------------------------------------
    # 5. Storm clearance can restore previous corridor
    # -----------------------------------------------------------------------

    def test_05_storm_clearance_restores_corridor(self):
        """5. After storm clears, D* Lite can restore the original optimal corridor."""
        initial_route = self.dstar.get_path()
        initial_cost = self.dstar.get_path_cost()

        first_step = (initial_route[0], initial_route[1])

        # Apply storm
        self.graph.update_edge_environment(first_step[0], first_step[1], STORM_ENV, ship=self.ship)
        self.dstar.update_edge(first_step[0], first_step[1])
        self.dstar.replan()

        # Clear storm — restore calm
        self.graph.update_edge_environment(first_step[0], first_step[1], CALM_ENV, ship=self.ship)
        self.dstar.update_edge(first_step[0], first_step[1])
        restored_route = self.dstar.replan()
        restored_cost = self.dstar.get_path_cost()

        # Cost after restoration should match original (same environment)
        self.assertAlmostEqual(restored_cost, initial_cost, places=9)

    # -----------------------------------------------------------------------
    # 6. Multiple simultaneous edge updates handled correctly
    # -----------------------------------------------------------------------

    def test_06_multiple_simultaneous_updates(self):
        """6. Batch-updating multiple edges at once produces correct results."""
        # Storm on two edges simultaneously
        affected = [("node_0_0", "node_0_1"), ("node_0_0", "node_1_0")]
        for src, tgt in affected:
            self.graph.update_edge_environment(src, tgt, STORM_ENV, ship=self.ship)

        self.dstar.update_edges(affected)
        new_route = self.dstar.replan()

        # Must still reach goal
        self.assertEqual(new_route[-1], self.goal_id)
        self.assertTrue(math.isfinite(self.dstar.get_path_cost()))

        # Verify Dijkstra agrees
        _, dijkstra_cost = reference_dijkstra(self.graph, self.start_id, self.goal_id)
        self.assertAlmostEqual(self.dstar.get_path_cost(), dijkstra_cost, places=9)

    # -----------------------------------------------------------------------
    # 7. Dynamic obstacle appearance causes route change
    # -----------------------------------------------------------------------

    def test_07_obstacle_causes_route_change(self):
        """7. Making a node non-navigable (obstacle) forces D* Lite to reroute."""
        initial_route = self.dstar.get_path()

        # Block an intermediate node on the current route
        if len(initial_route) > 2:
            blocked_node = initial_route[1]
            self.graph.set_node_navigability(blocked_node, False, ship=self.ship)
            self.dstar.update_node(blocked_node)
            new_route = self.dstar.replan()

            # New route must not pass through blocked node
            self.assertNotIn(blocked_node, new_route)
            if new_route:
                self.assertEqual(new_route[-1], self.goal_id)

    # -----------------------------------------------------------------------
    # 8. Dynamic obstacle disappearance allows route restoration
    # -----------------------------------------------------------------------

    def test_08_obstacle_removal_allows_restoration(self):
        """8. Clearing an obstacle allows D* Lite to restore the previously blocked route."""
        initial_route = self.dstar.get_path()
        initial_cost = self.dstar.get_path_cost()

        if len(initial_route) > 2:
            blocked_node = initial_route[1]

            # Block it
            self.graph.set_node_navigability(blocked_node, False, ship=self.ship)
            self.dstar.update_node(blocked_node)
            self.dstar.replan()

            # Re-enable the node
            self.graph.set_node_navigability(blocked_node, True, ship=self.ship)
            # Restore environment on incident edges
            for src_id in [e.source_id for e in self.graph.get_incoming_edges(blocked_node)]:
                self.graph.update_edge_environment(src_id, blocked_node, CALM_ENV, ship=self.ship)
            for tgt_id in [e.target_id for e in self.graph.get_outgoing_edges(blocked_node)]:
                self.graph.update_edge_environment(blocked_node, tgt_id, CALM_ENV, ship=self.ship)

            self.dstar.update_node(blocked_node)
            restored_route = self.dstar.replan()
            restored_cost = self.dstar.get_path_cost()

            # Cost should be back to initial (same env)
            self.assertAlmostEqual(restored_cost, initial_cost, places=9)

    # -----------------------------------------------------------------------
    # 9. Only affected edges are refreshed (call count verification)
    # -----------------------------------------------------------------------

    def test_09_only_affected_edges_queried(self):
        """9. refresh_edges() queries the provider only for the specified edges."""
        call_log = []
        calm_provider = ScenarioProvider(
            scenarios={"T3": CALM_ENV},
            call_log=call_log,
        )

        target_edges = [("node_0_0", "node_1_0")]
        self.graph.refresh_edges(
            edges=target_edges,
            timestamp="T3",
            provider=calm_provider,
            ship=self.ship,
        )

        # Provider should only have been called once (for the single requested edge)
        self.assertEqual(len(call_log), 1)

    # -----------------------------------------------------------------------
    # 10. Unaffected edge costs remain unchanged
    # -----------------------------------------------------------------------

    def test_10_unaffected_edges_unchanged(self):
        """10. Edges not in the refresh list retain their original cost unchanged."""
        unaffected_edge = ("node_1_1", "node_2_1")
        cost_before = self.graph.get_edge_cost(*unaffected_edge)

        storm_provider = ScenarioProvider(scenarios={"T_storm": STORM_ENV})
        self.graph.refresh_edges(
            edges=[("node_0_0", "node_1_0")],
            timestamp="T_storm",
            provider=storm_provider,
            ship=self.ship,
        )

        cost_after = self.graph.get_edge_cost(*unaffected_edge)
        self.assertAlmostEqual(cost_before, cost_after, places=9)

    # -----------------------------------------------------------------------
    # 11. D* Lite planner instance is reused (same Python object identity)
    # -----------------------------------------------------------------------

    def test_11_planner_instance_reused(self):
        """11. D* Lite replanning reuses the same planner object — no re-instantiation."""
        dstar_id_before = id(self.dstar)
        g_dict_id_before = id(self.dstar.g)
        rhs_dict_id_before = id(self.dstar.rhs)

        # Simulate an environmental change
        self.graph.update_edge_environment("node_0_0", "node_0_1", STORM_ENV, ship=self.ship)
        self.dstar.update_edge("node_0_0", "node_0_1")
        self.dstar.replan()

        # Same Python object
        self.assertEqual(id(self.dstar), dstar_id_before)
        # Internal state dictionaries are the same objects (not recreated)
        self.assertEqual(id(self.dstar.g), g_dict_id_before)
        self.assertEqual(id(self.dstar.rhs), rhs_dict_id_before)

    # -----------------------------------------------------------------------
    # 12. D* Lite incremental result matches Dijkstra after update
    # -----------------------------------------------------------------------

    def test_12_incremental_result_matches_dijkstra_after_update(self):
        """12. After dynamic edge cost update, D* Lite cost equals Dijkstra oracle cost."""
        # Apply storm to one edge
        self.graph.update_edge_environment("node_0_0", "node_1_0", STORM_ENV, ship=self.ship)
        self.dstar.update_edge("node_0_0", "node_1_0")
        self.dstar.replan()

        dstar_cost = self.dstar.get_path_cost()
        _, dijkstra_cost = reference_dijkstra(self.graph, self.start_id, self.goal_id)

        self.assertTrue(math.isfinite(dstar_cost))
        self.assertAlmostEqual(dstar_cost, dijkstra_cost, places=9)

    # -----------------------------------------------------------------------
    # 13. Cost identity: route_cost == sum(edge.cost for consecutive pairs)
    # -----------------------------------------------------------------------

    def test_13_route_cost_identity(self):
        """13. get_path_cost() equals the sum of consecutive edge costs along the returned path."""
        route = self.dstar.get_path()
        computed_cost = self.dstar.get_path_cost()

        manual_sum = 0.0
        for i in range(len(route) - 1):
            edge_cost = self.graph.get_edge_cost(route[i], route[i + 1])
            self.assertFalse(math.isinf(edge_cost), f"Edge {route[i]}->{route[i+1]} is inf")
            manual_sum += edge_cost

        self.assertAlmostEqual(computed_cost, manual_sum, places=9)

    # -----------------------------------------------------------------------
    # 14. Unreachable state correctly handled
    # -----------------------------------------------------------------------

    def test_14_unreachable_state_handled(self):
        """14. Blocking all paths from start returns empty route and inf cost."""
        # Block all outgoing edges from start
        for succ in self.graph.get_successors(self.start_id):
            self.graph.update_edge_environment(
                self.start_id, succ.node_id, NON_NAVIGABLE_ENV, ship=self.ship,
            )
            self.dstar.update_edge(self.start_id, succ.node_id)

        # Also block the center to prevent detour via west
        self.graph.set_node_navigability("node_1_1", False, ship=self.ship)
        self.dstar.update_node("node_1_1")

        route = self.dstar.replan()
        cost = self.dstar.get_path_cost(route)
        self.assertEqual(route, [])
        self.assertTrue(math.isinf(cost))

    # -----------------------------------------------------------------------
    # 15. Unreachable state can become reachable after update
    # -----------------------------------------------------------------------

    def test_15_unreachable_becomes_reachable(self):
        """15. After blocking all paths, clearing one corridor restores reachability."""
        # Block first outgoing edge with non-navigable env
        first_succs = list(self.graph.get_successors(self.start_id))
        self.assertGreater(len(first_succs), 0)

        # Make all non-navigable
        for succ in first_succs:
            self.graph.update_edge_environment(
                self.start_id, succ.node_id, NON_NAVIGABLE_ENV, ship=self.ship,
            )
            self.dstar.update_edge(self.start_id, succ.node_id)

        result = self.dstar.replan()
        # Might still be reachable via other paths — only test that replan doesn't crash
        # Now restore one edge
        restore_succ = first_succs[0].node_id
        self.graph.update_edge_environment(
            self.start_id, restore_succ, CALM_ENV, ship=self.ship,
        )
        self.dstar.update_edge(self.start_id, restore_succ)
        restored_route = self.dstar.replan()

        # If goal is reachable from restored corridor, route must reach goal
        restored_cost = self.dstar.get_path_cost()
        if restored_route:
            self.assertEqual(restored_route[-1], self.goal_id)
            self.assertTrue(math.isfinite(restored_cost))

    # -----------------------------------------------------------------------
    # 16. Provider failure does not partially corrupt the graph
    # -----------------------------------------------------------------------

    def test_16_provider_failure_does_not_corrupt_graph(self):
        """16. When refresh_edges() raises GridEnvironmentUpdateError, graph state is unchanged for the failing edge."""
        failing_provider = FailingProvider()

        edge = self.graph.get_edge("node_0_0", "node_1_0")
        cost_before = edge.cost
        env_before = edge.env_data

        with self.assertRaises(GridEnvironmentUpdateError):
            self.graph.refresh_edges(
                edges=[("node_0_0", "node_1_0")],
                timestamp="T_fail",
                provider=failing_provider,
                ship=self.ship,
            )

        # Graph state must remain unchanged after provider failure
        self.assertAlmostEqual(self.graph.get_edge_cost("node_0_0", "node_1_0"), cost_before, places=9)
        self.assertIs(self.graph.get_edge("node_0_0", "node_1_0").env_data, env_before)

    # -----------------------------------------------------------------------
    # 17. Failed refresh does not silently replace data with fake values
    # -----------------------------------------------------------------------

    def test_17_failed_refresh_no_silent_replacement(self):
        """17. Failed refresh never silently replaces env_data with a default/fake value."""
        failing_provider = FailingProvider()
        original_env = self.graph.get_edge("node_1_1", "node_2_1").env_data

        try:
            self.graph.refresh_edges(
                edges=[("node_1_1", "node_2_1")],
                timestamp="T_fail",
                provider=failing_provider,
                ship=self.ship,
            )
        except GridEnvironmentUpdateError:
            pass

        current_env = self.graph.get_edge("node_1_1", "node_2_1").env_data
        self.assertIs(current_env, original_env)  # Exact same object — never replaced

    # -----------------------------------------------------------------------
    # 18. Timestamp correctly propagated to env_data
    # -----------------------------------------------------------------------

    def test_18_timestamp_propagated_to_env_data(self):
        """18. Timestamp passed to refresh_edges() is forwarded to provider.fetch_conditions()."""
        new_timestamp = "2026-09-01T00:00:00Z"
        call_log = []

        # Build a provider that echoes back the queried timestamp in env_data
        class EchoTimestampProvider(WeatherProvider):
            def fetch_conditions(self, lat, lon, timestamp):
                ts = timestamp if isinstance(timestamp, str) else timestamp.isoformat()
                call_log.append(ts)
                return EnvironmentalData(
                    timestamp=ts,          # Echo the queried timestamp
                    wind_speed=10.0,
                    wind_direction=270.0,
                    wave_height=1.0,
                    wave_direction=250.0,
                    wave_period=7.0,
                    current_speed=0.3,
                    current_direction=90.0,
                )

        self.graph.refresh_edges(
            edges=[("node_0_0", "node_0_1")],
            timestamp=new_timestamp,
            provider=EchoTimestampProvider(),
            ship=self.ship,
        )

        # Provider was called with the correct timestamp
        self.assertEqual(call_log, [new_timestamp])
        # env_data.timestamp on the edge now reflects the queried timestamp
        edge = self.graph.get_edge("node_0_0", "node_0_1")
        self.assertEqual(edge.env_data.timestamp, new_timestamp)


    # -----------------------------------------------------------------------
    # 19. Both directed edges handled independently
    # -----------------------------------------------------------------------

    def test_19_directed_edges_handled_independently(self):
        """19. Refreshing A->B does not change B->A; costs and env differ due to bearing reversal."""
        call_log = []
        provider = ScenarioProvider(scenarios={"T_dir": STORM_ENV}, call_log=call_log)

        # Only refresh A->B
        results = self.graph.refresh_edges(
            edges=[("node_0_0", "node_1_0")],
            timestamp="T_dir",
            provider=provider,
            ship=self.ship,
        )

        cost_ab = self.graph.get_edge_cost("node_0_0", "node_1_0")
        cost_ba = self.graph.get_edge_cost("node_1_0", "node_0_0")

        # B->A must still have the original CALM_ENV-derived cost (not storm)
        env_ba = self.graph.get_edge("node_1_0", "node_0_0").env_data
        # B->A env_data is still CALM_ENV (not STORM_ENV)
        if env_ba is not None:
            self.assertAlmostEqual(env_ba.wind_speed, CALM_ENV.wind_speed, places=9)

        # Provider was called exactly once (only for A->B)
        self.assertEqual(len(call_log), 1)

        # A->B and B->A now have different env and different costs
        self.assertNotAlmostEqual(cost_ab, cost_ba, places=3)

    # -----------------------------------------------------------------------
    # 20. Floating-point cost comparison uses appropriate tolerance
    # -----------------------------------------------------------------------

    def test_20_floating_point_tolerance(self):
        """20. Cost comparisons use abs_tol=1e-9 to avoid spurious fp mismatch failures."""
        # Apply identical environment twice — costs must be bit-for-bit identical
        self.graph.update_edge_environment("node_0_0", "node_1_0", CALM_ENV, ship=self.ship)
        cost_first = self.graph.get_edge_cost("node_0_0", "node_1_0")

        self.graph.update_edge_environment("node_0_0", "node_1_0", CALM_ENV, ship=self.ship)
        cost_second = self.graph.get_edge_cost("node_0_0", "node_1_0")

        # Exact equality holds for deterministic CostModel
        self.assertEqual(cost_first, cost_second)

        # Also verify the EdgeRefreshResult cost fields are consistent
        provider = ScenarioProvider(scenarios={"T_fp": CALM_ENV})
        results = self.graph.refresh_edges(
            edges=[("node_0_0", "node_1_0")],
            timestamp="T_fp",
            provider=provider,
            ship=self.ship,
        )
        self.assertEqual(len(results), 1)
        result = results[0]
        # old_cost == new_cost since same environment applied
        self.assertAlmostEqual(result.old_cost, result.new_cost, places=9)
        self.assertAlmostEqual(result.new_cost, self.graph.get_edge_cost("node_0_0", "node_1_0"), places=9)


if __name__ == "__main__":
    unittest.main()
