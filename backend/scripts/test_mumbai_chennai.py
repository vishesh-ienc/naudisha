"""
Simulation script testing Mumbai -> Chennai navigation around the Indian Peninsula.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.routing.graph import GeographicGridGraph, GridConfig
from naudisha.routing.land_mask import is_point_on_land, is_segment_crossing_land, is_cross_peninsular_voyage
from naudisha.routing.dstar_lite import DStarLite
from naudisha.core.models import ShipProfile, EnvironmentalData, CostWeights
from naudisha.core.calculations import calculate_haversine_distance

def test_mumbai_to_chennai():
    # Mumbai Port: 18.95, 72.82 -> Chennai Port: 13.08, 80.27
    start_lat, start_lon = 18.95, 72.82
    dest_lat, dest_lon = 13.08, 80.27

    print(f"Planning route from Mumbai ({start_lat}, {start_lon}) to Chennai ({dest_lat}, {dest_lon})...")

    # 1. Bounding box computation with cross-peninsular expansion
    min_lat = min(start_lat, dest_lat)
    max_lat = max(start_lat, dest_lat)
    min_lon = min(start_lon, dest_lon)
    max_lon = max(start_lon, dest_lon)

    if is_cross_peninsular_voyage(start_lat, start_lon, dest_lat, dest_lon):
        print("  Cross-peninsular voyage detected! Expanding southern boundary past Cape Comorin/Sri Lanka...")
        # Southern tip of Sri Lanka is at ~5.9°N, so south boundary should be ~5.0°N
        min_lat = min(min_lat, 5.0)
        # Eastern tip of Sri Lanka is at ~81.9°E, so eastern boundary should be at least ~83.0°E
        max_lon = max(max_lon, 83.0)

    margin_lat = 0.5
    margin_lon = 0.5

    origin_lat = max(-90.0, min_lat - margin_lat)
    origin_lon = max(-180.0, min_lon - margin_lon)
    top_lat = min(90.0, max_lat + margin_lat)
    right_lon = min(180.0, max_lon + margin_lon)

    total_lat = top_lat - origin_lat
    total_lon = right_lon - origin_lon

    # Grid resolution ~0.5 deg (30 NM)
    res = 0.5
    rows = round(total_lat / res) + 1
    cols = round(total_lon / res) + 1

    lat_spacing = total_lat / max(rows - 1, 1)
    lon_spacing = total_lon / max(cols - 1, 1)

    print(f"  Grid: {rows} rows x {cols} cols ({rows * cols} nodes), Lat: [{origin_lat:.1f}, {top_lat:.1f}], Lon: [{origin_lon:.1f}, {right_lon:.1f}]")

    cfg = GridConfig(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        rows=rows,
        cols=cols,
        lat_spacing=lat_spacing,
        lon_spacing=lon_spacing,
    )

    graph = GeographicGridGraph(config=cfg)

    # 2. Mark land nodes and edges as non-navigable
    land_nodes = 0
    sea_nodes = 0
    for node in graph.get_all_nodes():
        if is_point_on_land(node.lat, node.lon):
            node.is_navigable = False
            land_nodes += 1
        else:
            sea_nodes += 1

    ship = ShipProfile(
        ship_type="Cargo",
        length=200.0,
        beam=32.0,
        draft=10.0,
        cruising_speed=14.0,
        maximum_speed=20.0,
    )
    # Populate baseline calm environment
    graph.populate_uniform_environment(
        env=EnvironmentalData(
            timestamp="2026-08-17T12:00:00Z",
            wind_speed=10.0,
            wind_direction=90.0,
            wave_height=1.0,
            wave_direction=90.0,
            wave_period=6.0,
            current_speed=0.2,
            current_direction=90.0,
        ),
        ship=ship,
        weights=CostWeights(),
    )

    # Also invalidate edges that cross land
    blocked_edges = 0
    for (src, tgt), edge in graph._edges.items():
        src_n = graph.get_node(src)
        tgt_n = graph.get_node(tgt)
        if not src_n.is_navigable or not tgt_n.is_navigable or is_segment_crossing_land(src_n.lat, src_n.lon, tgt_n.lat, tgt_n.lon):
            edge.is_navigable = False
            edge.cost = float("inf")
            blocked_edges += 1

    print(f"  Land nodes: {land_nodes}, Sea nodes: {sea_nodes}, Blocked edges: {blocked_edges}/{len(graph._edges)}")

    # 3. Find nearest navigable nodes
    def find_nearest(lat, lon):
        best_id = None
        best_dist = float("inf")
        for node in graph.get_all_nodes():
            if not node.is_navigable:
                continue
            dist = calculate_haversine_distance(lat, lon, node.lat, node.lon)
            if dist < best_dist:
                best_dist = dist
                best_id = node.node_id
        return best_id

    start_id = find_nearest(start_lat, start_lon)
    dest_id = find_nearest(dest_lat, dest_lon)
    s_node = graph.get_node(start_id)
    d_node = graph.get_node(dest_id)
    print(f"  Start Node: {start_id} at ({s_node.lat:.2f}, {s_node.lon:.2f})")
    print(f"  Dest Node: {dest_id} at ({d_node.lat:.2f}, {d_node.lon:.2f})")

    # 4. Run D* Lite
    dstar = DStarLite(graph=graph, start_id=start_id, goal_id=dest_id)
    reachable = dstar.compute_shortest_path()
    path = dstar.get_path()
    cost = dstar.get_path_cost()

    print(f"\nRouting Result:")
    print(f"  Reachable: {reachable}")
    print(f"  Path Node Count: {len(path) if path else 0}")
    print(f"  Total Cost: {cost:.2f}")

    if path:
        print(f"\nWaypoints:")
        for idx, nid in enumerate(path):
            n = graph.get_node(nid)
            print(f"    [{idx:2d}] ({n.lat:6.2f}N, {n.lon:6.2f}E) - {'LAND (ERROR!)' if is_point_on_land(n.lat, n.lon) else 'OCEAN'}")

if __name__ == "__main__":
    test_mumbai_to_chennai()
