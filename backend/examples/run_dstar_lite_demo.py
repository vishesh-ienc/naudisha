"""
NauDisha — D* Lite Incremental Route Planning & Dynamic Storm Replanning Demo
=============================================================================
Demonstrates:
1. Creating a 5x5 spatial navigation grid off the western coast of India.
2. Initializing dynamic environmental baseline conditions across all edges.
3. Running D* Lite to compute the initial optimal vessel route from origin to destination.
4. Simulating a dynamic severe storm developing on an active segment along the vessel's route.
5. Updating that single edge via CostModel in O(1) time and notifying D* Lite.
6. Performing incremental D* Lite replanning to find an optimal detour around the storm.
7. Demonstrating that the route adapts purely due to changing environmental dynamics.
"""

from __future__ import annotations

import math
import os
import sys

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha import (
    ShipProfile,
    EnvironmentalData,
    CostWeights,
    GridConfig,
    GeographicGridGraph,
    DStarLite,
)


def format_path(graph: GeographicGridGraph, path: list[str]) -> str:
    """Helper to format node path with geographic coordinates."""
    elements = []
    for nid in path:
        n = graph.get_node(nid)
        elements.append(f"{nid} ({n.lat:.1f}N, {n.lon:.1f}E)")
    return " ->\n       ".join(elements)


def main() -> None:
    print("======================================================================")
    print("   NauDisha - D* Lite Dynamic Ship Routing & Storm Replanning")
    print("======================================================================")

    # 1. Create Ship Profile (Container Ship)
    ship = ShipProfile(
        ship_type="Container Vessel (Panamax)",
        length=294.0,
        beam=32.2,
        draft=12.0,
        cruising_speed=18.0,
        maximum_speed=23.0,
    )
    print(f"\n[1] VESSEL PROFILE:")
    print(f"    Type:            {ship.ship_type}")
    print(f"    Cruising Speed:  {ship.cruising_speed} knots (Max: {ship.maximum_speed} knots)")

    # 2. Build 5x5 Navigation Grid (Arabian Sea Corridor)
    grid_cfg = GridConfig(
        origin_lat=18.0,  # 18.0° N (Mumbai offing)
        origin_lon=72.0,  # 72.0° E
        rows=5,
        cols=5,
        lat_spacing=0.5,  # ~30 NM per step
        lon_spacing=0.5,
    )
    graph = GeographicGridGraph(config=grid_cfg, default_ship=ship)

    print(f"\n[2] GEOGRAPHIC NAVIGATION GRID:")
    print(f"    Dimensions:      {grid_cfg.rows} rows x {grid_cfg.cols} cols ({len(graph.get_all_nodes())} waypoints)")
    print(f"    Origin:          ({grid_cfg.origin_lat:.2f} N, {grid_cfg.origin_lon:.2f} E)")
    print(f"    Coverage:        18.0 deg N - 20.0 deg N, 72.0 deg E - 74.0 deg E")

    # 3. Populate Uniform Baseline Environmental Conditions
    calm_env = EnvironmentalData(
        timestamp="2026-08-16T12:00:00Z",
        wind_speed=12.0,       # 12 knots breeze
        wind_direction=45.0,   # From NE
        wave_height=1.2,       # 1.2m slight sea
        wave_direction=45.0,
        wave_period=6.0,
        current_speed=1.2,     # 1.2 knot current
        current_direction=45.0,# Flowing towards NE (Favorable for NE-bound transit)
    )
    graph.populate_uniform_environment(env=calm_env, ship=ship)

    start_id = "node_0_0"  # SW corner (18.0 N, 72.0 E)
    goal_id = "node_4_4"   # NE corner (20.0 N, 74.0 E)

    print(f"\n[3] VOYAGE OBJECTIVE:")
    print(f"    Start Waypoint:  {start_id} (18.0 N, 72.0 E)")
    print(f"    Goal Waypoint:   {goal_id} (20.0 N, 74.0 E)")

    # 4. Plan Initial Optimal Route with D* Lite
    planner = DStarLite(graph=graph, start_id=start_id, goal_id=goal_id, heuristic_scale=0.0)
    initial_route = planner.plan()
    initial_cost = planner.get_path_cost()

    print("\n" + "-" * 70)
    print("   [4] INITIAL D* LITE OPTIMAL ROUTE (CALM BASELINE CONDITIONS)")
    print("-" * 70)
    print(f"    Total Route Cost: {initial_cost:.4f}")
    print(f"    Waypoints ({len(initial_route)} nodes):")
    print(f"       {format_path(graph, initial_route)}")

    # 5. Simulate Dynamic Weather Hazard: Severe Tropical Storm on an Active Route Edge
    # Select the second segment along the vessel's planned route
    hazard_edge_source = initial_route[0]
    hazard_edge_target = initial_route[1]

    print("\n" + "=" * 70)
    print(f"   [5] DYNAMIC ENVIRONMENTAL UPDATE: SEVERE STORM INTERCEPT")
    print(f"   Storm hits segment: '{hazard_edge_source}' -> '{hazard_edge_target}'")
    print("=" * 70)

    old_edge_cost = graph.get_edge_cost(hazard_edge_source, hazard_edge_target)

    # Severe storm conditions: 48kt gale, 6.5m rough seas, violent 3.0kt opposing current
    storm_env = EnvironmentalData(
        timestamp="2026-08-16T15:00:00Z",
        wind_speed=48.0,        # 48 knots gale
        wind_direction=0.0,     # Headwind
        wave_height=6.5,        # 6.5m dangerous waves
        wave_direction=0.0,
        wave_period=11.0,
        current_speed=3.0,      # Opposing current
        current_direction=180.0,
    )

    # Update edge environment in O(1) time through CostModel
    updated_cost = graph.update_edge_environment(
        source_id=hazard_edge_source,
        target_id=hazard_edge_target,
        env=storm_env,
        ship=ship,
    )

    print(f"    Initial Edge Cost:  {old_edge_cost:.4f}")
    print(f"    Updated Storm Cost: {updated_cost:.4f} (+{updated_cost - old_edge_cost:.4f} cost surge)")

    # 6. Notify D* Lite and Replan Incrementally
    planner.update_edge(hazard_edge_source, hazard_edge_target)
    new_route = planner.replan()
    new_cost = planner.get_path_cost()

    print("\n" + "-" * 70)
    print("   [6] D* LITE INCREMENTAL REPLANNED ROUTE (STORM DETOUR)")
    print("-" * 70)
    print(f"    New Route Cost:   {new_cost:.4f}")
    print(f"    Waypoints ({len(new_route)} nodes):")
    print(f"       {format_path(graph, new_route)}")

    # 7. Comparison & Validation
    # Independent verification oracle
    from tests.test_dstar_lite_correctness import reference_dijkstra
    oracle_path, oracle_cost = reference_dijkstra(graph, start_id, goal_id)

    print("\n" + "=" * 70)
    print("   [7] ROUTE COMPARISON & MATHEMATICAL VERIFICATION")
    print("=" * 70)
    print(f"    Initial Route:       {' -> '.join(initial_route)}")
    print(f"    Detoured Route:      {' -> '.join(new_route)}")
    
    avoided = not (new_route[0] == hazard_edge_source and new_route[1] == hazard_edge_target)
    print(f"    Avoided Storm ('{hazard_edge_source}' -> '{hazard_edge_target}'): {avoided}")
    print(f"    Cost without Detour (taking storm):    {initial_cost - old_edge_cost + updated_cost:.4f}")
    print(f"    Cost with D* Lite Optimal Detour:      {new_cost:.4f}")
    print(f"    Independent Dijkstra Oracle Cost:      {oracle_cost:.4f}")
    print(f"    Mathematical Optimality Verified:      {math.isclose(new_cost, oracle_cost, abs_tol=1e-5)} (D* Lite cost == Dijkstra oracle)")
    print("======================================================================")


if __name__ == "__main__":
    main()
