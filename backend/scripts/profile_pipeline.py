"""
Benchmark script for Phase 15 Before/After measurements.
Measures cold and objective-switch route planning across corridors.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.api.services import RoutePlanningService, objective_to_weights
from naudisha.core.models import ShipProfile
from naudisha.routing.dstar_lite import DStarLite
from datetime import datetime, timezone

def benchmark_corridor(name: str, start_lat: float, start_lon: float, dest_lat: float, dest_lon: float, objective: str = "balanced", service = None):
    print(f"\n========================================================")
    print(f"BENCHMARK: {name}")
    print(f"Start: ({start_lat}, {start_lon}) -> Dest: ({dest_lat}, {dest_lon}) | Objective: {objective}")
    print(f"========================================================")

    if service is None:
        service = RoutePlanningService()

    effective_ship = service.ship_profile
    effective_weights = objective_to_weights(objective)
    dep_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    t_start = time.perf_counter()

    # 1. Grid construction
    t0 = time.perf_counter()
    graph = service._build_bounding_grid(start_lat, start_lon, dest_lat, dest_lon, ship=effective_ship)
    t_grid = time.perf_counter() - t0

    num_nodes = len(graph.get_all_nodes())
    num_edges = len(graph._edges)

    # 2. Environmental Population & Cost Evaluation
    t0 = time.perf_counter()
    graph.populate_environment(
        timestamp=dep_iso,
        provider=service.environment_provider,
        ship=effective_ship,
        weights=effective_weights,
    )
    t_env = time.perf_counter() - t0

    # 3. Node mapping
    t0 = time.perf_counter()
    start_node_id = service._find_nearest_node_id(graph, start_lat, start_lon)
    dest_node_id = service._find_nearest_node_id(graph, dest_lat, dest_lon)
    t_nodes = time.perf_counter() - t0

    # 4. D* Lite Pathfinding
    t0 = time.perf_counter()
    dstar = DStarLite(graph=graph, start_id=start_node_id, goal_id=dest_node_id)
    reachable = dstar.compute_shortest_path()
    path = dstar.get_path()
    cost = dstar.get_path_cost()
    t_dstar = time.perf_counter() - t0

    # 5. Route metrics
    t0 = time.perf_counter()
    route_coords = []
    total_nm = 0.0
    for node_id in path:
        node = graph.get_node(node_id)
        if node:
            route_coords.append((round(node.lat, 4), round(node.lon, 4)))
    for i in range(len(path) - 1):
        edge = graph.get_edge(path[i], path[i + 1])
        if edge and edge.evaluation and edge.evaluation.metrics:
            total_nm += edge.evaluation.metrics.distance_nm
    t_recon = time.perf_counter() - t0

    total_time = time.perf_counter() - t_start

    print(f"Results:")
    print(f"  Nodes: {num_nodes}, Directed Edges: {num_edges}")
    print(f"  Path Waypoints: {len(path)}, Distance: {total_nm:.1f} nm, Cost: {cost:.2f}")
    print(f"Timing Breakdown:")
    print(f"  Grid Generation:      {t_grid * 1000:8.2f}ms")
    print(f"  Environment & Costs:  {t_env * 1000:8.2f}ms ({t_env:.2f}s)")
    print(f"  Node Mapping:         {t_nodes * 1000:8.2f}ms")
    print(f"  D* Lite:              {t_dstar * 1000:8.2f}ms")
    print(f"  Route Reconstruction: {t_recon * 1000:8.2f}ms")
    print(f"  TOTAL TIME:           {total_time * 1000:8.2f}ms ({total_time:.2f}s)")

    return {
        "name": name,
        "objective": objective,
        "nodes": num_nodes,
        "edges": num_edges,
        "waypoints": len(path),
        "distance_nm": round(total_nm, 1),
        "cost": round(cost, 2),
        "t_grid_ms": round(t_grid * 1000, 2),
        "t_env_s": round(t_env, 2),
        "t_dstar_ms": round(t_dstar * 1000, 2),
        "total_s": round(total_time, 2),
    }

if __name__ == "__main__":
    service = RoutePlanningService()
    # 1. Benchmark Mumbai to Kochi (Cold)
    r1 = benchmark_corridor("Mumbai to Kochi [Cold]", 18.85, 72.45, 9.96, 76.22, "balanced", service)

    # 2. Benchmark Mumbai to Kochi [Objective Switch: Fuel Efficiency] (Cached Corridor)
    r2 = benchmark_corridor("Mumbai to Kochi [Objective: Fuel Efficiency]", 18.85, 72.45, 9.96, 76.22, "fuel_efficiency", service)

    # 3. Benchmark Mumbai to Kochi [Objective Switch: Fastest] (Cached Corridor)
    r3 = benchmark_corridor("Mumbai to Kochi [Objective: Fastest]", 18.85, 72.45, 9.96, 76.22, "fastest", service)
