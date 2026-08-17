"""
Comprehensive Routing and Land Avoidance Diagnostic Matrix.
Tests end-to-end route calculation and nautical validity across all major Indian and Indian Ocean port pairs.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.api.services import RoutePlanningService
from naudisha.data.weather_provider import MockWeatherProvider
from naudisha.routing.land_mask import is_point_on_land

PORTS = [
    ("Mumbai (BOM)", 18.85, 72.45),
    ("JNPT (JNP)", 18.78, 72.55),
    ("Mundra (MND)", 22.72, 69.70),
    ("Kandla (KND)", 22.95, 70.15),
    ("Pipavav (PIP)", 20.90, 71.52),
    ("Hazira (HZR)", 21.08, 72.62),
    ("Mormugao (MRM)", 15.42, 73.75),
    ("Mangalore (NML)", 12.92, 74.78),
    ("Kochi (COK)", 9.96, 76.22),
    ("Tuticorin (TUT)", 8.75, 78.18),
    ("Chennai (MAA)", 13.10, 80.35),
    ("Kakinada (KKN)", 16.98, 82.28),
    ("Visakhapatnam (VTZ)", 17.68, 83.33),
    ("Paradip (PDP)", 20.25, 86.70),
    ("Kolkata/Haldia (HLD)", 21.90, 88.10),
    ("Colombo (CMB)", 6.95, 79.82),
    ("Hambantota (HBT)", 6.11, 81.12),
]

def run_diagnostics():
    service = RoutePlanningService(environment_provider=MockWeatherProvider())

    # Curated set of representative corridor routes covering:
    # 1. West Coast internal
    # 2. Gulf of Kutch to West Coast
    # 3. Cross-Peninsular (West <-> East)
    # 4. East Coast internal
    # 5. India to Sri Lanka
    test_pairs = [
        ("Mumbai", "Mundra"),
        ("Mundra", "Kochi"),
        ("Kandla", "Chennai"),
        ("Mumbai", "Kochi"),
        ("Mumbai", "Chennai"),
        ("Mormugao", "Visakhapatnam"),
        ("Mangalore", "Paradip"),
        ("Kochi", "Kolkata/Haldia"),
        ("Tuticorin", "Chennai"),
        ("Chennai", "Visakhapatnam"),
        ("Visakhapatnam", "Kolkata/Haldia"),
        ("Mumbai", "Colombo"),
        ("Chennai", "Colombo"),
        ("Mundra", "Hambantota"),
        ("Kolkata/Haldia", "Mumbai"),
    ]

    ports_dict = {name.split()[0]: (lat, lon) for name, lat, lon in PORTS}

    print("=========================================================================================")
    print("NAUDISHA ROUTING ENGINE DIAGNOSTIC MATRIX")
    print("=========================================================================================")
    print(f"{'Corridor':<35} | {'Status':<8} | {'Waypoints':<9} | {'Dist (nm)':<10} | {'Land Hits':<9} | {'Time (ms)'}")
    print("-----------------------------------------------------------------------------------------")

    passes = 0
    failures = 0

    for orig_name, dest_name in test_pairs:
        s_lat, s_lon = ports_dict[orig_name]
        d_lat, d_lon = ports_dict[dest_name]
        corridor_label = f"{orig_name} -> {dest_name}"

        t0 = time.perf_counter()
        try:
            res = service.plan_preview_route(
                imo_number="DIAG_IMO",
                start_lat=s_lat,
                start_lon=s_lon,
                dest_lat=d_lat,
                dest_lon=d_lon,
                optimization_objective="balanced",
            )
            t_elapsed = (time.perf_counter() - t0) * 1000.0

            land_hits = 0
            for w_lat, w_lon in res.route:
                if is_point_on_land(w_lat, w_lon):
                    land_hits += 1

            status = "PASS" if land_hits == 0 else "LAND_ERR"
            if land_hits == 0:
                passes += 1
            else:
                failures += 1

            print(f"{corridor_label:<35} | {status:<8} | {len(res.route):<9} | {res.distance_nm:<10.1f} | {land_hits:<9} | {t_elapsed:.1f}ms")

        except Exception as exc:
            t_elapsed = (time.perf_counter() - t0) * 1000.0
            failures += 1
            print(f"{corridor_label:<35} | {'FAIL':<8} | {'-':<9} | {'-':<10} | {'-':<9} | {t_elapsed:.1f}ms ({type(exc).__name__})")

    print("=========================================================================================")
    print(f"DIAGNOSTIC SUMMARY: {passes} PASSED, {failures} FAILED out of {len(test_pairs)} test corridors.")
    print("=========================================================================================")

if __name__ == "__main__":
    run_diagnostics()
