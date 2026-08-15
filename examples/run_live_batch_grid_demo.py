"""
NauDisha — Live Batch Grid Routing Demo
========================================
Demonstrates the batch environmental sampling optimization:

    80 edge midpoints → 1 CMEMS currents + 1 CMEMS waves request → local nearest-point extraction
    + Open-Meteo wind (deduplicated by grid cell)
    → D* Lite optimal route
    → Dijkstra oracle verification

Compares request counts and timing against the old per-edge approach.
"""

from __future__ import annotations

import heapq
import math
import time
from datetime import datetime, timezone

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    CostWeights,
)
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.data.wind_provider import OpenMeteoWindProvider
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.weather_provider import BatchCapableProvider
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
)
from naudisha.routing.dstar_lite import DStarLite


# ---------------------------------------------------------------------------
# Reference Dijkstra Oracle
# ---------------------------------------------------------------------------

def dijkstra_oracle(graph: GeographicGridGraph, start_id: str, goal_id: str):
    """Independent Dijkstra implementation for cross-verification."""
    dist = {nid: math.inf for nid in graph._nodes}
    dist[start_id] = 0.0
    prev = {nid: None for nid in graph._nodes}
    pq = [(0.0, start_id)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == goal_id:
            break
        for neighbor in graph.get_neighbors(u):
            neighbor_id = neighbor.node_id
            edge_cost = graph.get_edge_cost(u, neighbor_id)
            alt = dist[u] + edge_cost
            if alt < dist[neighbor_id]:
                dist[neighbor_id] = alt
                prev[neighbor_id] = u
                heapq.heappush(pq, (alt, neighbor_id))

    path = []
    current = goal_id
    while current is not None:
        path.append(current)
        current = prev[current]
    path.reverse()

    return path, dist[goal_id]


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("   NauDisha Live Batch Grid Routing Demo")
    print("   Copernicus Marine + Open-Meteo → Batch Sampling → D* Lite")
    print("=" * 72)

    # ---- Grid specification ----
    config = GridConfig(
        origin_lat=17.50,
        origin_lon=70.50,
        rows=5,
        cols=5,
        lat_spacing=0.25,
        lon_spacing=0.25,
    )
    ship = ShipProfile(
        ship_type="Bulk Carrier",
        length=225.0,
        beam=32.2,
        draft=10.5,
        cruising_speed=14.0,
        maximum_speed=16.5,
    )
    timestamp = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    start_id = "node_0_0"
    goal_id = "node_4_4"

    n_nodes = config.rows * config.cols
    graph = GeographicGridGraph(config=config, default_ship=ship)
    n_edges = len(graph._edges)

    print(f"\n{'─' * 72}")
    print(f"[1] GEOGRAPHIC GRID SPECIFICATION")
    print(f"{'─' * 72}")
    print(f"    Region:               Arabian Sea / Western India")
    print(f"    Dimensions:           {config.rows} x {config.cols} ({n_nodes} Waypoint Nodes)")
    print(f"    Origin (SW Corner):   ({config.origin_lat:.2f}N, {config.origin_lon:.2f}E)")
    print(f"    Grid Step:            {config.lat_spacing} deg")
    print(f"    Directed Edges:       {n_edges}")
    print(f"    Voyage:               {start_id} --> {goal_id}")

    # ---- Create batch-capable composite provider ----
    marine_provider = CopernicusMarineProvider(enable_cache=True)
    wind_provider = OpenMeteoWindProvider(enable_cache=True)
    composite_provider = CompositeEnvironmentalProvider(
        marine_provider=marine_provider,
        wind_provider=wind_provider,
    )

    assert isinstance(composite_provider, BatchCapableProvider), (
        "CompositeEnvironmentalProvider must implement BatchCapableProvider"
    )

    print(f"\n{'─' * 72}")
    print(f"[2] LIVE BATCH ENVIRONMENT POPULATION (DATA SOURCE: LIVE)")
    print(f"{'─' * 72}")
    print(f"    Timestamp:            {timestamp.isoformat()}")
    print(f"    Marine data:          Copernicus Marine Service (batch bounding-box query)")
    print(f"    Wind data:            Open-Meteo (deduplicated grid cells)")
    print(f"    Edge midpoints:       {n_edges}")
    print(f"    Expected CMEMS calls: 1 currents + 1 waves = 2")
    print()

    t0 = time.perf_counter()
    graph.populate_environment(
        timestamp=timestamp,
        provider=composite_provider,
        ship=ship,
    )
    t_populate = time.perf_counter() - t0

    print(f"\n    Population time:      {t_populate:.2f} seconds")

    # Count finite-cost edges
    finite_edges = sum(
        1 for (s, t) in graph._edges if math.isfinite(graph.get_edge_cost(s, t))
    )
    print(f"    Finite-cost edges:    {finite_edges}/{n_edges}")

    # ---- Sample edge data ----
    print(f"\n{'─' * 72}")
    print(f"[3] SAMPLE EDGE CONDITIONS")
    print(f"{'─' * 72}")
    sample_edges = list(graph._edges.keys())[:3]
    for (src, tgt) in sample_edges:
        edge = graph._edges[(src, tgt)]
        env = edge.env_data
        mid_lat, mid_lon = graph.get_edge_midpoint(src, tgt)
        print(f"    {src} → {tgt}:")
        print(f"      Midpoint:     ({mid_lat:.2f}N, {mid_lon:.2f}E)")
        if env:
            print(f"      Current:      {env.current_speed:.2f} kn @ {env.current_direction:.1f}°")
            print(f"      Waves:        Hs={env.wave_height:.2f}m, dir={env.wave_direction:.1f}°, Tp={env.wave_period:.1f}s")
            print(f"      Wind:         {env.wind_speed:.1f} kn @ {env.wind_direction:.1f}°")
        print(f"      Cost:         {edge.cost:.4f}")

    # ---- D* Lite ----
    print(f"\n{'─' * 72}")
    print(f"[4] D* LITE OPTIMAL ROUTE")
    print(f"{'─' * 72}")

    t0 = time.perf_counter()
    dstar = DStarLite(graph=graph, start_id=start_id, goal_id=goal_id)
    route = dstar.plan()
    route_cost = dstar.get_path_cost()
    t_dstar = time.perf_counter() - t0

    print(f"    Route:    {' → '.join(route)}")
    print(f"    Cost:     {route_cost:.6f}")
    print(f"    D* Lite:  {t_dstar * 1000:.1f} ms")

    # ---- Dijkstra oracle ----
    print(f"\n{'─' * 72}")
    print(f"[5] DIJKSTRA ORACLE VERIFICATION")
    print(f"{'─' * 72}")

    dij_path, dij_cost = dijkstra_oracle(graph, start_id, goal_id)
    delta = abs(route_cost - dij_cost)

    print(f"    Dijkstra: {' → '.join(dij_path)}")
    print(f"    Cost:     {dij_cost:.6f}")
    print(f"    Delta:    {delta:.2e}")

    if delta < 1e-9:
        print(f"    ✅ MATHEMATICAL MATCH (delta < 1e-9)")
    else:
        print(f"    ⚠ MISMATCH (delta = {delta})")

    # ---- Summary ----
    print(f"\n{'─' * 72}")
    print(f"[6] PERFORMANCE SUMMARY")
    print(f"{'─' * 72}")
    print(f"    Grid:                 {config.rows}×{config.cols} ({n_edges} edges)")
    print(f"    Old architecture:     {n_edges} edges × 2 CMEMS calls = {n_edges * 2} requests")
    print(f"    New architecture:     1 currents + 1 waves = 2 CMEMS requests")
    print(f"    Request reduction:    {n_edges * 2} → 2 ({n_edges * 2 // 2}x reduction)")
    print(f"    Population time:      {t_populate:.2f}s (was ~{n_edges * 12}s sequential)")
    print(f"    D* Lite time:         {t_dstar * 1000:.1f}ms")
    print(f"    Oracle match:         {'YES ✅' if delta < 1e-9 else 'NO ❌'}")

    print(f"\n{'=' * 72}")
    print(f"   Demo complete.")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
