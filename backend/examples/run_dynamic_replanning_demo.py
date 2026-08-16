"""
NauDisha Dynamic Environmental Replanning Demonstration
=======================================================
Demonstrates the complete dynamic routing pipeline:

    Copernicus Marine + Open-Meteo (LIVE)
        -> CompositeEnvironmentalProvider
        -> GeographicGridGraph (5x5, Arabian Sea)
        -> CostModel (edge costs)
        -> D* Lite (optimal route)
        -> [SIMULATED STORM] (deterministic scenario)
        -> Selective refresh_edges()
        -> Incremental D* Lite replan (same planner instance)
        -> [STORM CLEARED]
        -> Another incremental replan
        -> Independent Dijkstra oracle verification at each stage

All live data is clearly labelled as LIVE.
All simulated storm data is clearly labelled as SIMULATED.
No fabricated values are presented as real observations.

Run:
    python examples/run_dynamic_replanning_demo.py
"""

from __future__ import annotations

import heapq
import math
import time
from datetime import datetime, timezone
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
    GridEnvironmentUpdateError,
    EdgeRefreshResult,
)
from naudisha.routing.dstar_lite import DStarLite
from naudisha.data.composite_provider import CompositeEnvironmentalProvider

DIVIDER = "=" * 70
SECTION = "-" * 70

# ---------------------------------------------------------------------------
# Reference Dijkstra oracle
# ---------------------------------------------------------------------------

def reference_dijkstra(
    graph: GeographicGridGraph,
    start_id: str,
    goal_id: str,
) -> Tuple[List[str], float]:
    """Independent Dijkstra reference oracle (used for verification only)."""
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


def verify_against_dijkstra(
    dstar: DStarLite,
    graph: GeographicGridGraph,
    start_id: str,
    goal_id: str,
    phase_label: str,
) -> None:
    """Runs Dijkstra oracle and prints comparison result."""
    t0 = time.perf_counter()
    _, dijkstra_cost = reference_dijkstra(graph, start_id, goal_id)
    dijkstra_ms = (time.perf_counter() - t0) * 1000.0

    dstar_cost = dstar.get_path_cost()
    delta = abs(dstar_cost - dijkstra_cost)
    match = math.isclose(dstar_cost, dijkstra_cost, abs_tol=1e-9)

    print(f"    D* Lite cost ({phase_label}):     {dstar_cost:.6f}")
    print(f"    Dijkstra cost ({phase_label}):    {dijkstra_cost:.6f}")
    print(f"    Absolute delta:                   {delta:.2e}")
    print(f"    Dijkstra oracle time:             {dijkstra_ms:.1f} ms")
    result_label = "MATHEMATICAL MATCH [PASSED]" if match else "DISCREPANCY [FAILED]"
    print(f"    Optimality result:                {result_label}")


# ---------------------------------------------------------------------------
# Main demonstration
# ---------------------------------------------------------------------------

def main() -> None:
    print(DIVIDER)
    print("   NauDisha Dynamic Environmental Replanning Demonstration")
    print("   Copernicus Marine + Open-Meteo -> D* Lite -> Incremental Replan")
    print(DIVIDER)

    # -----------------------------------------------------------------------
    # Grid and vessel configuration
    # -----------------------------------------------------------------------
    rows, cols = 5, 5
    origin_lat, origin_lon = 17.5, 70.5
    lat_spacing, lon_spacing = 0.25, 0.25

    config = GridConfig(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        rows=rows,
        cols=cols,
        lat_spacing=lat_spacing,
        lon_spacing=lon_spacing,
    )

    ship = ShipProfile(
        ship_type="Panamax Bulk Carrier",
        length=230.0,
        beam=32.0,
        draft=12.5,
        cruising_speed=14.0,
        maximum_speed=18.0,
    )

    # Start: SW corner, Goal: NE corner
    start_id = "node_0_0"
    goal_id = f"node_{rows - 1}_{cols - 1}"

    # Timestamp for live data
    timestamp = "2026-08-15T12:00:00Z"

    # -----------------------------------------------------------------------
    # [1] Grid Specification
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[1] GEOGRAPHIC NAVIGATION GRID SPECIFICATION")
    print(SECTION)
    lat_max = origin_lat + (rows - 1) * lat_spacing
    lon_max = origin_lon + (cols - 1) * lon_spacing
    step_nm = lat_spacing * 60.0  # approximate degrees to nautical miles

    print(f"    Region:               Arabian Sea / Western India")
    print(f"    Dimensions:           {rows} x {cols} ({rows * cols} Waypoint Nodes)")
    print(f"    Origin (SW Corner):   ({origin_lat:.2f}N, {origin_lon:.2f}E)")
    print(f"    Boundaries:           Lat [{origin_lat:.2f}N - {lat_max:.2f}N], "
          f"Lon [{origin_lon:.2f}E - {lon_max:.2f}E]")
    print(f"    Grid Step:            {lat_spacing:.2f} deg (~{step_nm:.1f} NM)")
    total_edges = 2 * (rows * (cols - 1) + (rows - 1) * cols)
    print(f"    Directed Edges:       {total_edges}")
    print(f"    Voyage:               {start_id} --> {goal_id}")

    # -----------------------------------------------------------------------
    # [2] Live Environmental Grid Population
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print(f"[2] INITIAL LIVE ENVIRONMENT (DATA SOURCE: LIVE)")
    print(SECTION)
    print(f"    Timestamp:            {timestamp}")
    print(f"    Marine data:          Copernicus Marine Service (currents + waves)")
    print(f"    Wind data:            Open-Meteo (10m surface winds)")
    print(f"    Edge sampling:        Geographic midpoint of each directed edge")
    print()

    graph = GeographicGridGraph(config=config, default_ship=ship)
    provider = CompositeEnvironmentalProvider()

    try:
        graph.populate_environment(
            timestamp=timestamp,
            provider=provider,
            ship=ship,
        )
        print(f"    [+] Grid environment populated: {total_edges} edges with live data")
    except GridEnvironmentUpdateError as e:
        print(f"    [!] LIVE ENVIRONMENT FETCH FAILED: {e}")
        print(f"    Aborting demo. Check Copernicus Marine credentials and network access.")
        return

    # Show 4 representative edges
    print()
    print(f"    {'Edge':<26} {'Midpoint':<18} {'Current':>14} {'Wave':>8} {'Wind':>16} {'Cost':>7}")
    print(f"    {'-' * 92}")
    sample_pairs = [
        ("node_0_0", "node_0_1"),
        ("node_0_0", "node_1_0"),
        ("node_2_2", "node_2_3"),
        ("node_3_3", "node_4_3"),
    ]
    for src, tgt in sample_pairs:
        edge = graph.get_edge(src, tgt)
        if edge and edge.env_data:
            mid = graph.get_edge_midpoint(src, tgt)
            curr = f"{edge.env_data.current_speed:.2f}kn@{edge.env_data.current_direction:.0f}d"
            wave = f"{edge.env_data.wave_height:.2f}m"
            wind = f"{edge.env_data.wind_speed:.1f}kn@{edge.env_data.wind_direction:.0f}d"
            print(f"    {src} -> {tgt:<6} ({mid[0]:.2f}N,{mid[1]:.2f}E)  {curr:>14} {wave:>8} {wind:>16} {edge.cost:>7.4f}")

    # -----------------------------------------------------------------------
    # [3] Initial D* Lite Route + Oracle
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print(f"[3] INITIAL D* LITE OPTIMAL ROUTE")
    print(SECTION)

    t0 = time.perf_counter()
    dstar = DStarLite(graph=graph, start_id=start_id, goal_id=goal_id)
    reachable = dstar.compute_shortest_path()
    initial_plan_ms = (time.perf_counter() - t0) * 1000.0

    if not reachable:
        print("    [!] Destination unreachable on initial live grid. Aborting.")
        return

    initial_route = dstar.get_path()
    initial_cost = dstar.get_path_cost()

    print(f"    Route:                {' -> '.join(initial_route)}")
    print(f"    Waypoints:            {len(initial_route)}")
    print(f"    Accumulated Cost:     {initial_cost:.4f}")

    total_nm = sum(
        graph.get_edge(initial_route[i], initial_route[i + 1]).evaluation.metrics.distance_nm
        for i in range(len(initial_route) - 1)
        if graph.get_edge(initial_route[i], initial_route[i + 1]) and
           graph.get_edge(initial_route[i], initial_route[i + 1]).evaluation
    )
    print(f"    Estimated Distance:   {total_nm:.2f} NM")
    print(f"    D* Lite planning:     {initial_plan_ms:.1f} ms")
    print()
    verify_against_dijkstra(dstar, graph, start_id, goal_id, "initial")

    # -----------------------------------------------------------------------
    # [4] Simulated Storm Intercept
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[4] SIMULATED STORM INTERCEPT  [DATA SOURCE: SIMULATED - NOT LIVE]")
    print(SECTION)
    print("    NOTE: The following storm conditions are a SIMULATED deterministic scenario.")
    print("    They are NOT real Copernicus Marine or Open-Meteo observations.")
    print()

    # Apply storm to the first two edges of the initial route
    storm_edges = []
    if len(initial_route) >= 2:
        storm_edges.append((initial_route[0], initial_route[1]))
    if len(initial_route) >= 3:
        storm_edges.append((initial_route[1], initial_route[2]))

    SIMULATED_STORM = EnvironmentalData(
        timestamp="SIMULATED_T_STORM",
        wind_speed=45.0,       # Severe gale (45 knots)
        wind_direction=0.0,    # Direct headwind northbound
        wave_height=5.5,       # Very rough sea (5.5 m Hs)
        wave_direction=0.0,    # Head seas
        wave_period=14.0,      # Long swell period
        current_speed=2.5,     # Strong opposing current
        current_direction=180.0,  # Opposing vessel direction
    )

    print(f"    Simulated storm applied to corridor:")
    print(f"    Wind:    {SIMULATED_STORM.wind_speed:.0f} knots headwind")
    print(f"    Waves:   {SIMULATED_STORM.wave_height:.1f} m Hs, head seas")
    print(f"    Current: {SIMULATED_STORM.current_speed:.1f} knots opposing")
    print()

    for src, tgt in storm_edges:
        old_cost = graph.get_edge_cost(src, tgt)
        new_cost = graph.update_edge_environment(src, tgt, SIMULATED_STORM, ship=ship)
        print(f"    Edge {src} -> {tgt}:")
        print(f"      Old cost: {old_cost:.4f}")
        print(f"      New cost: {new_cost:.4f}  (+{new_cost - old_cost:.4f})")

    # -----------------------------------------------------------------------
    # [5] Selective Edge Refresh + D* Lite Incremental Replan
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[5] INCREMENTAL D* LITE REPLAN (STORM)")
    print(SECTION)

    dstar_id_before = id(dstar)

    t0 = time.perf_counter()
    for src, tgt in storm_edges:
        dstar.update_edge(src, tgt)
    storm_route = dstar.replan()
    storm_plan_ms = (time.perf_counter() - t0) * 1000.0

    storm_cost = dstar.get_path_cost()

    print(f"    D* Lite planner reused:   {'YES (same object)' if id(dstar) == dstar_id_before else 'NO'}")
    print(f"    Graph rebuilt:            NO")
    print(f"    Replanning time:          {storm_plan_ms:.2f} ms")
    print()
    print(f"    INITIAL ROUTE:   {' -> '.join(initial_route)}")
    print(f"    STORM ROUTE:     {' -> '.join(storm_route) if storm_route else '[UNREACHABLE]'}")
    print(f"    Storm avoided:   {'YES' if storm_route != initial_route else 'NO (same route chosen as cheaper)'}")
    print(f"    Initial cost:    {initial_cost:.4f}")
    print(f"    Storm cost:      {storm_cost:.4f}")
    print()
    verify_against_dijkstra(dstar, graph, start_id, goal_id, "storm")

    # -----------------------------------------------------------------------
    # [6] Storm Clearance + Second Replan
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[6] STORM CLEARANCE  [DATA SOURCE: SIMULATED - NOT LIVE]")
    print(SECTION)
    print("    NOTE: Storm clearance restores LIVE Copernicus + Open-Meteo conditions.")
    print("    This is a SIMULATED return to the initial live environment.")
    print()

    # Restore original live env data (re-query each edge from provider)
    from naudisha.data.weather_provider import WeatherProvider as WP

    class StoredEnvProvider(WP):
        """Returns the pre-stored environment for specific edges (after storm clearance)."""
        def __init__(self, edge_envs: Dict[Tuple[str, str], EnvironmentalData]) -> None:
            self.edge_envs = edge_envs
        def fetch_conditions(self, lat, lon, timestamp):
            # Match by approximate midpoint
            for (src, tgt), env in self.edge_envs.items():
                return env  # Return first match — single-edge usage
            raise RuntimeError("No matching env found.")

    cleared_edges_count = 0
    for src, tgt in storm_edges:
        old_cost = graph.get_edge_cost(src, tgt)
        # Re-fetch from live provider for the cleared edge
        mid_lat, mid_lon = graph.get_edge_midpoint(src, tgt)
        try:
            cleared_env = provider.fetch_conditions(lat=mid_lat, lon=mid_lon, timestamp=timestamp)
            new_cost = graph.update_edge_environment(src, tgt, cleared_env, ship=ship)
            print(f"    Edge {src} -> {tgt} cleared (LIVE data restored):")
            print(f"      Storm cost: {old_cost:.4f}")
            print(f"      Cleared cost: {new_cost:.4f}  ({new_cost - old_cost:+.4f})")
            cleared_edges_count += 1
        except Exception as e:
            print(f"    [!] Failed to re-fetch live data for {src}->{tgt}: {e}")
            print(f"    Falling back to initial CALM environment for storm-cleared edge.")
            FALLBACK_CALM = EnvironmentalData(
                timestamp="SIMULATED_T_CLEARED",
                wind_speed=12.0,
                wind_direction=270.0,
                wave_height=1.5,
                wave_direction=250.0,
                wave_period=7.0,
                current_speed=0.4,
                current_direction=90.0,
            )
            new_cost = graph.update_edge_environment(src, tgt, FALLBACK_CALM, ship=ship)
            print(f"      Cleared cost (simulated calm): {new_cost:.4f}")

    # -----------------------------------------------------------------------
    # [7] Post-Clearance Incremental Replan + Final Oracle
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[7] INCREMENTAL D* LITE REPLAN (STORM CLEARED)")
    print(SECTION)

    t0 = time.perf_counter()
    for src, tgt in storm_edges:
        dstar.update_edge(src, tgt)
    cleared_route = dstar.replan()
    cleared_plan_ms = (time.perf_counter() - t0) * 1000.0

    cleared_cost = dstar.get_path_cost()

    print(f"    D* Lite planner reused:   {'YES (same object)' if id(dstar) == dstar_id_before else 'NO'}")
    print(f"    Replanning time:          {cleared_plan_ms:.2f} ms")
    print()
    print(f"    STORM ROUTE:     {' -> '.join(storm_route) if storm_route else '[UNREACHABLE]'}")
    print(f"    CLEARED ROUTE:   {' -> '.join(cleared_route) if cleared_route else '[UNREACHABLE]'}")
    print(f"    Cost comparison: storm={storm_cost:.4f} -> cleared={cleared_cost:.4f}")
    print()
    verify_against_dijkstra(dstar, graph, start_id, goal_id, "cleared")

    # -----------------------------------------------------------------------
    # [8] Performance Summary
    # -----------------------------------------------------------------------
    print(f"\n{SECTION}")
    print("[8] PERFORMANCE TIMING SUMMARY")
    print(SECTION)
    print(f"    Initial D* Lite planning:     {initial_plan_ms:.2f} ms")
    print(f"    Storm incremental replan:     {storm_plan_ms:.2f} ms")
    print(f"    Clearance incremental replan: {cleared_plan_ms:.2f} ms")
    print()
    print("    NOTE: Timing is measured on a single small grid and is indicative only.")
    print("    D* Lite's advantage is incremental state reuse under repeated environmental")
    print("    changes, not necessarily raw speed on small static graphs.")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{DIVIDER}")
    print("   DYNAMIC REPLANNING DEMONSTRATION COMPLETED")
    print(f"   Initial -> Storm -> Cleared: {len(initial_route)} -> "
          f"{len(storm_route) if storm_route else 0} -> "
          f"{len(cleared_route) if cleared_route else 0} waypoints")
    print(f"   D* Lite planner instance reused: YES (no graph rebuild, no planner reset)")
    print(DIVIDER)


if __name__ == "__main__":
    main()
