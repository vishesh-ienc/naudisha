"""
NauDisha — Geographic Grid & Dynamic Environment Demonstration
================================================================
Demonstrates:
1. Creating a spatial geographic grid graph (GeographicGridGraph)
2. Assigning baseline environmental conditions across all edges
3. Calculating initial edge costs using CostModel
4. Dynamically updating environmental forecast on a single edge
5. Recalculating only that edge in O(1) time and observing the cost delta
6. Marking an obstacle / non-navigable waypoint and observing infinite cost enforcement
"""

from __future__ import annotations

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
)


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Geographic Grid & Routing Environment Layer Demo")
    print("======================================================================")

    # 1. Create Ship Profile
    ship = ShipProfile(
        ship_type="Container Vessel",
        length=295.0,
        beam=38.0,
        draft=11.5,
        cruising_speed=16.0,
        maximum_speed=21.0,
    )
    print(f"\n[1] VESSEL: {ship.ship_type} (Cruising: {ship.cruising_speed} kts, Max: {ship.maximum_speed} kts)")

    # 2. Configure 3x3 Navigation Grid
    grid_cfg = GridConfig(
        origin_lat=18.0,  # 18.0° N (Mumbai offing)
        origin_lon=72.0,  # 72.0° E
        rows=3,
        cols=3,
        lat_spacing=0.5,  # ~30 NM per cell
        lon_spacing=0.5,
    )
    graph = GeographicGridGraph(config=grid_cfg, default_ship=ship)

    print(f"\n[2] GRID GRAPH CONSTRUCTED:")
    print(f"    Dimensions:   {grid_cfg.rows} rows x {grid_cfg.cols} cols ({len(graph.get_all_nodes())} nodes)")
    print(f"    Origin:       ({grid_cfg.origin_lat:.2f} N, {grid_cfg.origin_lon:.2f} E)")
    print(f"    Resolution:   {grid_cfg.lat_spacing} deg lat x {grid_cfg.lon_spacing} deg lon")
    print(f"    Total Edges:  {len(graph.get_all_edges())} directed segments (4-direction)")

    # 3. Populate Uniform Baseline Weather
    calm_env = EnvironmentalData(
        timestamp="2026-08-16T12:00:00Z",
        wind_speed=12.0,       # 12 knots breeze
        wind_direction=45.0,   # NE
        wave_height=1.2,       # 1.2m slight sea
        wave_direction=45.0,
        wave_period=6.0,
        current_speed=1.0,     # 1 knot current
        current_direction=0.0, # Flowing North
    )
    graph.populate_uniform_environment(env=calm_env, ship=ship)

    edge_id = ("node_0_0", "node_1_0")
    initial_edge = graph.get_edge(*edge_id)
    initial_cost = initial_edge.cost
    initial_metrics = initial_edge.evaluation.metrics
    initial_scores = initial_edge.evaluation.scores

    print(f"\n[3] BASELINE EVALUATION FOR EDGE '{edge_id[0]}' -> '{edge_id[1]}':")
    print(f"    Navigating:       North (Bearing: {initial_metrics.bearing:.1f} deg)")
    print(f"    Distance:         {initial_metrics.distance_nm:.2f} NM")
    print(f"    Effective Speed:  {initial_metrics.effective_speed:.2f} kts (Current: {initial_metrics.along_track_current:+.2f} kts)")
    print(f"    Travel Time:      {initial_metrics.travel_time_hours:.2f} hrs")
    print(f"    Scores:           Time: {initial_scores.time_score:.3f}, Fuel: {initial_scores.fuel_score:.3f}, "
          f"Wind: {initial_scores.wind_score:.3f}, Wave: {initial_scores.wave_score:.3f}, Safety: {initial_scores.safety_score:.3f}")
    print(f"    INITIAL COST:     {initial_cost:.4f}")

    # 4. Dynamic Forecast Change: Localized Storm on Edge (node_0_0 -> node_1_0)
    print("\n" + "-" * 70)
    print("   [4] INJECTING DYNAMIC WEATHER UPDATE ON SPECIFIC EDGE")
    print("   Severe Storm: 40kt Headwind, 5.5m Waves, 2.5kt Opposing Current")
    print("-" * 70)

    storm_env = EnvironmentalData(
        timestamp="2026-08-16T14:00:00Z",
        wind_speed=40.0,        # 40 kt gale
        wind_direction=0.0,     # From North (direct headwind)
        wave_height=5.5,        # 5.5m rough seas
        wave_direction=0.0,
        wave_period=10.0,
        current_speed=2.5,      # Opposing current
        current_direction=180.0,# Flowing South
    )

    # Update in O(1) time
    updated_cost = graph.update_edge_environment(
        source_id=edge_id[0],
        target_id=edge_id[1],
        env=storm_env,
        ship=ship,
    )

    updated_edge = graph.get_edge(*edge_id)
    up_metrics = updated_edge.evaluation.metrics
    up_scores = updated_edge.evaluation.scores

    print(f"\n[5] UPDATED EVALUATION FOR EDGE '{edge_id[0]}' -> '{edge_id[1]}':")
    print(f"    Effective Speed:  {up_metrics.effective_speed:.2f} kts (Current: {up_metrics.along_track_current:+.2f} kts)")
    print(f"    Travel Time:      {up_metrics.travel_time_hours:.2f} hrs (Delay: +{up_metrics.travel_time_hours - initial_metrics.travel_time_hours:.2f} hrs)")
    print(f"    Scores:           Time: {up_scores.time_score:.3f}, Fuel: {up_scores.fuel_score:.3f}, "
          f"Wind: {up_scores.wind_score:.3f}, Wave: {up_scores.wave_score:.3f}, Safety: {up_scores.safety_score:.3f}")
    print(f"    UPDATED COST:     {updated_cost:.4f} (Cost Delta: +{updated_cost - initial_cost:.4f})")

    # 6. Obstacle / Non-Navigable Node Demo
    print("\n" + "-" * 70)
    print("   [6] MARKING WAYPOINT 'node_1_1' AS NON-NAVIGABLE (ISLAND/OBSTACLE)")
    print("-" * 70)
    graph.set_node_navigability("node_1_1", is_navigable=False, ship=ship)

    print(f"    Node 'node_1_1' Navigable:          {graph.is_node_navigable('node_1_1')}")
    print(f"    Edge 'node_0_1' -> 'node_1_1' Cost: {graph.get_edge_cost('node_0_1', 'node_1_1')}")
    print(f"    Edge 'node_1_1' -> 'node_2_1' Cost: {graph.get_edge_cost('node_1_1', 'node_2_1')}")
    print(f"    Unrelated 'node_0_0' -> 'node_0_1': {graph.get_edge_cost('node_0_0', 'node_0_1'):.4f} (Navigable: {graph.is_edge_navigable('node_0_0', 'node_0_1')})")

    print("\n======================================================================")
    print("   DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("======================================================================")


if __name__ == "__main__":
    main()
