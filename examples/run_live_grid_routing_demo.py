"""
NauDisha — Live Environmental Data Integration & D* Lite Routing Demo
=====================================================================
Demonstrates:
1. Creating a GeographicGridGraph over the Arabian Sea / Western India maritime corridor.
2. Injecting CompositeEnvironmentalProvider (Copernicus currents & waves + Open-Meteo wind).
3. Populating grid edges with real-time oceanographic and atmospheric data at edge midpoints.
4. Dynamically computing edge costs through NauDisha's multi-factor CostModel.
5. Executing D* Lite incremental pathfinding to obtain the optimal voyage route.
6. Cross-verifying route optimality against an independent reference Dijkstra solver.
"""

from __future__ import annotations

import heapq
import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.core.models import ShipProfile, CostWeights
from naudisha.cost.model import CostModel
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.copernicus_provider import CopernicusAuthenticationError, CopernicusProviderError
from naudisha.data.wind_provider import WindProviderError
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
    GridEnvironmentUpdateError,
)
from naudisha.routing.dstar_lite import DStarLite


def reference_dijkstra(
    graph: GeographicGridGraph,
    start_id: str,
    goal_id: str,
) -> Tuple[List[str], float]:
    """
    Independent reference Dijkstra algorithm used strictly as a verification oracle.
    Computes global shortest path on the populated graph.
    """
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


def main() -> None:
    print("======================================================================")
    print("   NauDisha — Live Environmental Data Routing Grid Demo")
    print("   (Copernicus Marine + Open-Meteo -> CostModel -> Grid -> D* Lite)")
    print("======================================================================")

    # 1. Setup Navigation Grid Configuration (Open Arabian Sea Maritime Corridor)
    origin_lat = 18.00  # South boundary
    origin_lon = 71.00  # West boundary (Offshore Arabian Sea)
    rows, cols = 3, 3
    lat_spacing, lon_spacing = 0.50, 0.50

    config = GridConfig(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        rows=rows,
        cols=cols,
        lat_spacing=lat_spacing,
        lon_spacing=lon_spacing,
    )

    ship = ShipProfile(
        ship_type="Container Vessel (Panamax)",
        length=294.0,
        beam=32.2,
        draft=12.0,
        cruising_speed=18.0,
        maximum_speed=23.0,
    )

    weights = CostWeights(
        time=1.5,
        fuel=1.2,
        wind=1.0,
        wave=1.0,
        current=0.8,
        safety=2.0,
    )

    cost_model = CostModel(default_weights=weights)

    # -------------------------------------------------------------------------
    # [1] GRID INITIALIZATION
    # -------------------------------------------------------------------------
    print("\n----------------------------------------------------------------------")
    print("[1] GEOGRAPHIC NAVIGATION GRID SPECIFICATION")
    print("----------------------------------------------------------------------")
    print(f"    Region:               Arabian Sea / Western Coast of India")
    print(f"    Dimensions:           {rows} x {cols} ({rows * cols} Waypoint Nodes)")
    print(f"    Origin (SW Corner):   ({origin_lat:.2f}N, {origin_lon:.2f}E)")
    print(f"    Boundaries:           Lat [{origin_lat:.2f}N - {origin_lat + (rows-1)*lat_spacing:.2f}N], "
          f"Lon [{origin_lon:.2f}E - {origin_lon + (cols-1)*lon_spacing:.2f}E]")
    print(f"    Grid Step:            {lat_spacing:.2f} deg (~{lat_spacing * 60:.1f} NM)")
    print(f"    Directed Edges:       24 (4-connected planar movement: N, S, E, W)")

    composite_provider = CompositeEnvironmentalProvider()
    graph = GeographicGridGraph(
        config=config,
        cost_model=cost_model,
        default_ship=ship,
        default_weights=weights,
        environment_provider=composite_provider,
    )

    # -------------------------------------------------------------------------
    # [2] LIVE DATA POPULATION
    # -------------------------------------------------------------------------
    query_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
    print("\n----------------------------------------------------------------------")
    print(f"[2] POPULATING LIVE ENVIRONMENTAL CONDITIONS (Timestamp: {query_timestamp})")
    print("----------------------------------------------------------------------")
    print("    - Querying Copernicus Marine Service (Ocean Currents & Spectral Waves)")
    print("    - Querying Open-Meteo API (10m Surface Wind Vectors)")
    print("    - Spatial Strategy: Sampling at Directed Edge Geographic Midpoints\n")

    try:
        graph.populate_environment(timestamp=query_timestamp)
        print("    [+] Grid environment population completed successfully.")
    except CopernicusAuthenticationError as auth_err:
        print("\n" + "=" * 70)
        print("   LIVE DATA FETCH FAILED — COPERNICUS AUTHENTICATION REQUIRED")
        print("=" * 70)
        print(f"    Reason:  {auth_err}")
        print("    Action:  Please run 'copernicusmarine login' in your terminal.")
        print("=" * 70)
        return
    except GridEnvironmentUpdateError as update_err:
        print("\n" + "=" * 70)
        print("   LIVE DATA FETCH FAILED — PROVIDER OUTAGE OR TIMEOUT")
        print("=" * 70)
        print(f"    Reason:  {update_err}")
        print("=" * 70)
        return
    except Exception as exc:
        print(f"\n[!] Unexpected Error during grid population: {exc}")
        return

    # -------------------------------------------------------------------------
    # [3] LIVE EDGE COSTS SUMMARY
    # -------------------------------------------------------------------------
    print("\n----------------------------------------------------------------------")
    print("[3] REPRESENTATIVE POPULATED DIRECTED EDGES & LIVE COSTS")
    print("----------------------------------------------------------------------")
    print(f"    {'Edge':<18} {'Midpoint':<18} {'Current':<16} {'Waves (Hs)':<12} {'Wind':<14} {'Cost':<8}")
    print("    " + "-" * 86)

    sample_edge_ids = [
        ("node_0_0", "node_1_0"),
        ("node_1_0", "node_0_0"),
        ("node_0_0", "node_0_1"),
        ("node_1_1", "node_2_1"),
        ("node_1_1", "node_1_2"),
        ("node_1_2", "node_2_2"),
    ]

    for src, tgt in sample_edge_ids:
        edge = graph.get_edge(src, tgt)
        if edge and edge.env_data:
            mid_lat, mid_lon = graph.get_edge_midpoint(src, tgt)
            curr_str = f"{edge.env_data.current_speed:.2f}kn @ {edge.env_data.current_direction:.0f} deg"
            wave_str = f"{edge.env_data.wave_height:.2f}m"
            wind_str = f"{edge.env_data.wind_speed:.1f}kn @ {edge.env_data.wind_direction:.0f} deg"
            print(f"    {src} -> {tgt:<6} ({mid_lat:.2f}N,{mid_lon:.2f}E)  {curr_str:<16} {wave_str:<12} {wind_str:<14} {edge.cost:.4f}")

    # -------------------------------------------------------------------------
    # [4] D* LITE ROUTE PLANNING
    # -------------------------------------------------------------------------
    start_id = "node_0_0"
    goal_id = f"node_{rows-1}_{cols-1}"

    print("\n----------------------------------------------------------------------")
    print(f"[4] D* LITE PATHFINDING (Voyage: {start_id} -> {goal_id})")
    print("----------------------------------------------------------------------")

    dstar = DStarLite(graph=graph, start_id=start_id, goal_id=goal_id)
    reachable = dstar.compute_shortest_path()
    route = dstar.get_path()
    total_cost = dstar.get_path_cost()

    if not reachable or not route:
        print("    [!] Destination unreachable due to non-navigable maritime conditions.")
        return

    print(f"    Optimal Route:        {' -> '.join(route)}")
    print(f"    Total Waypoints:      {len(route)}")
    print(f"    Accumulated Cost:     {total_cost:.4f}")

    # Compute total voyage distance and travel time from edge evaluations
    total_nm = 0.0
    total_hours = 0.0
    for i in range(len(route) - 1):
        edge = graph.get_edge(route[i], route[i + 1])
        if edge and edge.evaluation:
            total_nm += edge.evaluation.metrics.distance_nm
            total_hours += edge.evaluation.metrics.travel_time_hours

    print(f"    Total Distance:       {total_nm:.2f} NM")
    print(f"    Estimated Transit:    {total_hours:.2f} hours (~{total_hours / 24.0:.2f} days)")

    # -------------------------------------------------------------------------
    # [5] ORACLE VERIFICATION AGAINST INDEPENDENT DIJKSTRA
    # -------------------------------------------------------------------------
    print("\n----------------------------------------------------------------------")
    print("[5] VERIFICATION AGAINST INDEPENDENT DIJKSTRA ORACLE")
    print("----------------------------------------------------------------------")
    dijkstra_path, dijkstra_cost = reference_dijkstra(graph, start_id, goal_id)

    print(f"    D* Lite Cost:         {total_cost:.6f}")
    print(f"    Dijkstra Oracle Cost: {dijkstra_cost:.6f}")
    cost_diff = abs(total_cost - dijkstra_cost)
    print(f"    Absolute Cost Delta:  {cost_diff:.6e}")

    if math.isclose(total_cost, dijkstra_cost, abs_tol=1e-5):
        print("    Result:               MATHEMATICAL MATCH (100% Globally Optimal) [PASSED] [OK]")
    else:
        print("    Result:               DISCREPANCY DETECTED [FAILED] [X]")

    print("\n======================================================================")
    print("   LIVE ENVIRONMENTAL ROUTING GRID DEMONSTRATION COMPLETED")
    print("======================================================================")


if __name__ == "__main__":
    main()
