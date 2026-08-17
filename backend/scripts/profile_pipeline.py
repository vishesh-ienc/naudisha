"""
Phase 16 Route Calculation Latency Optimization & Environmental Pipeline Benchmark.
Measures cold, warm, and objective-switching performance across standard Indian Ocean corridors.
"""

import time
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

from naudisha.api.services import RoutePlanningService, objective_to_weights
from naudisha.core.models import ShipProfile
from naudisha.routing.land_mask import is_point_on_land, is_segment_crossing_land


def benchmark_corridor(
    service: RoutePlanningService,
    name: str,
    start_lat: float,
    start_lon: float,
    dest_lat: float,
    dest_lon: float,
    objective: str = "balanced",
    departure_time: str = None,
) -> Dict[str, Any]:
    dep_iso = departure_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    t0 = time.perf_counter()
    res = service.plan_preview_route(
        imo_number=None,
        start_lat=start_lat,
        start_lon=start_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        timestamp=dep_iso,
        optimization_objective=objective,
    )
    total_ms = (time.perf_counter() - t0) * 1000.0
    
    land_hits = sum(1 for pt in res.route if is_point_on_land(pt[0], pt[1]))
    
    metrics = {
        "corridor": name,
        "objective": objective,
        "total_ms": round(total_ms, 2),
        "distance_nm": res.distance_nm,
        "duration_hours": res.estimated_time_hours,
        "total_cost": res.total_cost,
        "waypoints": len(res.route),
        "legs": len(res.legs),
        "land_hits": land_hits,
        "env_source": getattr(res, "environment_source", "unknown"),
    }
    return metrics


if __name__ == "__main__":
    service = RoutePlanningService()
    
    test_corridors = [
        ("Mumbai -> Kochi", 18.95, 72.82, 9.93, 76.26),
        ("Mumbai -> Colombo", 18.95, 72.82, 6.94, 79.85),
        ("Mumbai -> Singapore", 18.95, 72.82, 1.28, 103.85),
        ("Mumbai -> Mombasa", 18.95, 72.82, -4.05, 39.67),
    ]
    
    print("=" * 95)
    print("PHASE 16 BENCHMARK MATRIX — COLD vs WARM vs OBJECTIVE SWITCHING")
    print("=" * 95)
    
    cold_results = []
    warm_results = []
    
    # 1. COLD RUN
    print("\n[STAGE 1] COLD RUN (First Request per Corridor — Environment Ingestion & Graph Build)")
    for name, s_lat, s_lon, d_lat, d_lon in test_corridors:
        m = benchmark_corridor(service, name, s_lat, s_lon, d_lat, d_lon, objective="balanced")
        cold_results.append(m)
        print(f"  {name:22} | Time: {m['total_ms']:7.2f} ms | Dist: {m['distance_nm']:7.1f} NM | Waypoints: {m['waypoints']:2} | Land Hits: {m['land_hits']} | Source: {m['env_source']}")

    # 2. WARM RUN (Identical Request — Cache Hit)
    print("\n[STAGE 2] WARM RUN (Subsequent Request — Level 2 Corridor Cache Hit)")
    for name, s_lat, s_lon, d_lat, d_lon in test_corridors:
        m = benchmark_corridor(service, name, s_lat, s_lon, d_lat, d_lon, objective="balanced")
        warm_results.append(m)
        print(f"  {name:22} | Time: {m['total_ms']:7.2f} ms | Dist: {m['distance_nm']:7.1f} NM | Waypoints: {m['waypoints']:2} | Land Hits: {m['land_hits']} | Source: {m['env_source']}")

    # 3. OBJECTIVE SWITCHING (Mumbai -> Singapore across Balanced, Fuel Efficiency, Fastest, Safety)
    print("\n[STAGE 3] OBJECTIVE SWITCHING (Mumbai -> Singapore Reusing Environmental Spatial Data)")
    objectives = ["balanced", "fuel_efficiency", "fastest", "safety"]
    for obj in objectives:
        m = benchmark_corridor(service, "Mumbai -> Singapore", 18.95, 72.82, 1.28, 103.85, objective=obj)
        print(f"  Objective: {obj:15} | Time: {m['total_ms']:7.2f} ms | Dist: {m['distance_nm']:7.1f} NM | Duration: {m['duration_hours']:5.1f} h | Cost: {m['total_cost']:7.2f} | Hits: {m['land_hits']}")

    print("\n" + "=" * 95)
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 95)
