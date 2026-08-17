"""
Test script validating 8-Directional D* Lite with Line-of-Sight Nautical Path Smoothing.
"""

import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.routing.graph import GeographicGridGraph, GridConfig
from naudisha.routing.land_mask import is_point_on_land, is_segment_crossing_land, is_cross_peninsular_voyage
from naudisha.routing.dstar_lite import DStarLite
from naudisha.core.models import ShipProfile, EnvironmentalData, CostWeights
from naudisha.core.calculations import calculate_haversine_distance

DIRECTIONS_8 = [
    (1, 0, "N"),
    (-1, 0, "S"),
    (0, 1, "E"),
    (0, -1, "W"),
    (1, 1, "NE"),
    (1, -1, "NW"),
    (-1, 1, "SE"),
    (-1, -1, "SW"),
]

def test_smooth_corridor(name, start_lat, start_lon, dest_lat, dest_lon):
    print(f"\n=======================================================")
    print(f"TESTING NAUTICAL SMOOTHING: {name}")
    print(f"Start: ({start_lat}, {start_lon}) -> Dest: ({dest_lat}, {dest_lon})")
    print(f"=======================================================")

    is_cross = is_cross_peninsular_voyage(start_lat, start_lon, dest_lat, dest_lon)
    is_kutch = (start_lat >= 22.0 and 69.0 <= start_lon <= 70.8) or (dest_lat >= 22.0 and 69.0 <= dest_lon <= 70.8)
    is_gulf = (start_lon <= 56.5 and start_lat >= 24.0) or (dest_lon <= 56.5 and dest_lat >= 24.0)

    min_lat = min(start_lat, dest_lat)
    max_lat = max(start_lat, dest_lat)
    min_lon = min(start_lon, dest_lon)
    max_lon = max(start_lon, dest_lon)

    if is_cross:
        min_lat = min(min_lat, 5.0)
        max_lon = max(max_lon, 83.0)
        min_lon = min(min_lon, 72.0)
    if is_kutch:
        min_lon = min(min_lon, 68.4)
        max_lat = max(max_lat, 23.2)
    if is_gulf:
        max_lat = max(max_lat, 27.0)

    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon

    margin_lat = max(0.30, lat_span * 0.15)
    margin_lon = max(0.30, lon_span * 0.15)

    origin_lat = max(-90.0, min_lat - margin_lat)
    origin_lon = max(-180.0, min_lon - margin_lon)
    top_lat = min(90.0, max_lat + margin_lat)
    right_lon = min(180.0, max_lon + margin_lon)

    total_lat = top_lat - origin_lat
    total_lon = right_lon - origin_lon

    res = 0.50  # ~30 NM resolution
    max_dim = 35 if (is_cross or is_kutch or is_gulf) else 25
    rows = max(6, min(max_dim, round(total_lat / res) + 1))
    cols = max(6, min(max_dim, round(total_lon / res) + 1))

    lat_spacing = total_lat / max(rows - 1, 1)
    lon_spacing = total_lon / max(cols - 1, 1)

    cfg = GridConfig(origin_lat=origin_lat, origin_lon=origin_lon, rows=rows, cols=cols, lat_spacing=lat_spacing, lon_spacing=lon_spacing)
    ship = ShipProfile(ship_type="Container", length=300, beam=40, draft=12, cruising_speed=18, maximum_speed=24)
    graph = GeographicGridGraph(config=cfg, default_ship=ship)

    # Rebuild edges with 8 directions
    graph._edges.clear()
    for n in graph._nodes.values():
        graph._outgoing[n.node_id].clear()
        graph._incoming[n.node_id].clear()

    for r in range(rows):
        for c in range(cols):
            s_id = graph._grid_lookup[(r, c)]
            s_node = graph._nodes[s_id]
            for dr, dc, _ in DIRECTIONS_8:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    t_id = graph._grid_lookup[(nr, nc)]
                    t_node = graph._nodes[t_id]
                    from naudisha.core.models import SegmentData
                    from naudisha.routing.graph import GridEdge
                    seg = SegmentData(start_lat=s_node.lat, start_lon=s_node.lon, end_lat=t_node.lat, end_lon=t_node.lon, is_navigable=True)
                    edge = GridEdge(source_id=s_id, target_id=t_id, segment=seg, env_data=None, cost=float('inf'), is_navigable=True)
                    graph._edges[(s_id, t_id)] = edge
                    graph._outgoing[s_id].add(t_id)
                    graph._incoming[t_id].add(s_id)

    graph.populate_uniform_environment(
        env=EnvironmentalData(timestamp="2026-08-17T12:00:00Z", wind_speed=10, wind_direction=90, wave_height=1, wave_direction=90, wave_period=6, current_speed=0.2, current_direction=90),
        ship=ship,
        weights=CostWeights(),
    )

    # Apply land mask
    for node in graph.get_all_nodes():
        if is_point_on_land(node.lat, node.lon):
            node.is_navigable = False

    for (src, tgt), edge in graph._edges.items():
        s_node = graph.get_node(src)
        t_node = graph.get_node(tgt)
        if not s_node.is_navigable or not t_node.is_navigable or is_segment_crossing_land(s_node.lat, s_node.lon, t_node.lat, t_node.lon):
            edge.is_navigable = False
            edge.cost = float('inf')

    def find_nearest(lat, lon):
        best_id = None
        best_dist = float('inf')
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

    dstar = DStarLite(graph=graph, start_id=start_id, goal_id=dest_id)
    reachable = dstar.compute_shortest_path()
    path = dstar.get_path()

    print(f"  D* Lite Reachable: {reachable}, Raw 8-dir Waypoints: {len(path) if path else 0}")
    if not path:
        return

    raw_coords = [(start_lat, start_lon)]
    for nid in path:
        n = graph.get_node(nid)
        raw_coords.append((n.lat, n.lon))
    raw_coords.append((dest_lat, dest_lon))

    # Line of sight smoothing
    smoothed = [raw_coords[0]]
    curr = 0
    while curr < len(raw_coords) - 1:
        farthest = curr + 1
        for next_i in range(len(raw_coords) - 1, curr, -1):
            p1 = raw_coords[curr]
            p2 = raw_coords[next_i]
            if not is_segment_crossing_land(p1[0], p1[1], p2[0], p2[1], samples=25):
                farthest = next_i
                break
        smoothed.append(raw_coords[farthest])
        curr = farthest

    # Interpolate for smooth visual tracking
    dense_track = [smoothed[0]]
    max_leg_nm = 40.0
    for i in range(len(smoothed) - 1):
        p1 = smoothed[i]
        p2 = smoothed[i + 1]
        dist_nm = calculate_haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if dist_nm > max_leg_nm:
            steps = max(1, round(dist_nm / max_leg_nm))
            lats = np.linspace(p1[0], p2[0], steps + 1)[1:]
            lons = np.linspace(p1[1], p2[1], steps + 1)[1:]
            for lat, lon in zip(lats, lons):
                dense_track.append((float(lat), float(lon)))
        else:
            dense_track.append(p2)

    total_dist = 0.0
    for i in range(len(dense_track) - 1):
        total_dist += calculate_haversine_distance(dense_track[i][0], dense_track[i][1], dense_track[i+1][0], dense_track[i+1][1])

    print(f"  Smoothed Waypoints: {len(smoothed)}, Interpolated Track Points: {len(dense_track)}, Total Distance: {total_dist:.1f} nm")
    print(f"  Key Waypoint Course Breakdown:")
    for idx, (w_lat, w_lon) in enumerate(smoothed):
        print(f"    WP {idx:2d}: ({w_lat:6.2f}N, {w_lon:6.2f}E)")

if __name__ == "__main__":
    test_smooth_corridor("Mumbai to Dubai (UAE)", 18.85, 72.45, 25.30, 55.30)
    test_smooth_corridor("Mumbai to Colombo (Sri Lanka)", 18.85, 72.45, 6.95, 79.82)
    test_smooth_corridor("Mumbai to Chennai (India Trans-Peninsular)", 18.85, 72.45, 13.10, 80.35)
    test_smooth_corridor("Mumbai to Mundra (Gulf of Kutch)", 18.85, 72.45, 22.72, 69.70)
