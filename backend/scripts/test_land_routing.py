"""
Integration test for Maritime Routing with Indian Ocean Land Masking.
Tests realistic ocean navigation across all major Indian Ocean corridors using official port pilot boarding stations.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.api.services import RoutePlanningService
from naudisha.data.weather_provider import MockWeatherProvider
from naudisha.routing.land_mask import is_point_on_land

def test_routes():
    # Use deterministic mock provider for rapid corridor route topology testing
    service = RoutePlanningService(environment_provider=MockWeatherProvider())

    corridors = [
        ("Mumbai to Chennai (Cross-Peninsular)", 18.85, 72.45, 13.10, 80.35),
        ("Mumbai to Kochi (West Coast)", 18.85, 72.45, 9.96, 76.22),
        ("Chennai to Visakhapatnam (East Coast)", 13.10, 80.35, 17.68, 83.30),
        ("Kolkata to Chennai (Bay of Bengal)", 21.50, 88.10, 13.10, 80.35),
        ("Mumbai to Colombo (India to Sri Lanka)", 18.85, 72.45, 6.94, 79.80),
    ]

    print("=================================================================")
    print("TESTING MARITIME ROUTING & LAND AVOIDANCE ACROSS CORRIDORS")
    print("=================================================================")

    for name, s_lat, s_lon, d_lat, d_lon in corridors:
        print(f"\nTesting: {name}")
        print(f"  Start: ({s_lat}, {s_lon}) -> Dest: ({d_lat}, {d_lon})")

        res = service.plan_preview_route(
            imo_number="TEST_LAND",
            start_lat=s_lat,
            start_lon=s_lon,
            dest_lat=d_lat,
            dest_lon=d_lon,
            optimization_objective="balanced",
        )

        waypoints = res.route
        print(f"  Result: {len(waypoints)} waypoints, Distance: {res.distance_nm:.1f} nm, Cost: {res.total_cost:.2f}")

        # Check that NO waypoint falls on land
        land_hits = 0
        for i, (w_lat, w_lon) in enumerate(waypoints):
            on_land = is_point_on_land(w_lat, w_lon)
            if on_land:
                print(f"  [ERROR] Waypoint [{i}] ({w_lat}, {w_lon}) is on LAND!")
                land_hits += 1

        if land_hits == 0:
            print(f"  [PASS] All {len(waypoints)} waypoints are 100% in open navigable ocean!")
            print(f"    Origin departure: ({waypoints[0][0]:.2f}N, {waypoints[0][1]:.2f}E)")
            mid_idx = len(waypoints) // 2
            print(f"    Midway transit:   ({waypoints[mid_idx][0]:.2f}N, {waypoints[mid_idx][1]:.2f}E)")
            print(f"    Final arrival:    ({waypoints[-1][0]:.2f}N, {waypoints[-1][1]:.2f}E)")
        else:
            print(f"  [FAIL] {land_hits} waypoints were found on land!")

if __name__ == "__main__":
    test_routes()
