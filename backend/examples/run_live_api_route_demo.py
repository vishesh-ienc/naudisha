"""
NauDisha — Live Environmental Route Planning API Demo (Phase 8.2)
==================================================================
Demonstrates:
1. Orchestrating RoutePlanningService with CompositeEnvironmentalProvider.
2. Fetching real-time Copernicus Marine (currents/waves) & Open-Meteo (wind) observations
   using the high-performance Phase 7.5 batch environmental pipeline.
3. Dynamically constructing a navigation grid covering the Arabian Sea corridor.
4. Executing D* Lite dynamic pathfinding to compute the optimal marine route.
5. Emitting a contract-compliant JSON response structure adhering to docs/API_CONTRACT.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.api.services import RoutePlanningService
from naudisha.api.schemas import Coordinate, RoutePreviewResponse
from naudisha.api.errors import (
    EnvironmentUnavailableError,
    RouteNotFoundError,
    APIException,
)
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.copernicus_provider import (
    CopernicusAuthenticationError,
    CopernicusProviderError,
    CopernicusMarineProvider,
)
from naudisha.data.wind_provider import OpenMeteoWindProvider, WindProviderError


def run_live_api_route_demo() -> None:
    print("=" * 75)
    print("   NauDisha — Live Environmental Route Planning API Demo (Phase 8.2)")
    print("   [DATA SOURCE: LIVE — Copernicus Marine Service + Open-Meteo]")
    print("=" * 75)

    # 1. Define Voyage Request Parameters (Arabian Sea Corridor)
    imo_number = "9451234"
    start_lat = 18.00
    start_lon = 71.00
    dest_lat = 19.00
    dest_lon = 72.00
    utc_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")

    print("\n----------------------------------------------------------------------")
    print("[1] INCOMING VOYAGE ROUTE PREVIEW REQUEST")
    print("----------------------------------------------------------------------")
    print(f"    Vessel IMO:           {imo_number}")
    print(f"    Departure Point:      ({start_lat:.2f}N, {start_lon:.2f}E) [Offshore Arabian Sea]")
    print(f"    Destination Point:    ({dest_lat:.2f}N, {dest_lon:.2f}E) [Mumbai Approach Corridor]")
    print(f"    Observation Time:     {utc_timestamp}")
    print(f"    Corridor Span:        ~{abs(dest_lat - start_lat):.2f} deg Lat x {abs(dest_lon - start_lon):.2f} deg Lon")

    # 2. Initialize Service Layer with Composite Environmental Provider
    print("\n----------------------------------------------------------------------")
    print("[2] INITIALIZING ROUTE PLANNING SERVICE")
    print("----------------------------------------------------------------------")
    print("    - Environmental Provider: CompositeEnvironmentalProvider (Batch Capable)")
    print("    - Ocean Hydrodynamics:   Copernicus Marine (Currents + Spectral Waves)")
    print("    - Atmospheric Weather:   Open-Meteo API (10m Surface Wind Vectors)")
    print("    - Routing Algorithm:      D* Lite Dynamic Pathfinding Engine")
    print("    - Multi-Factor Cost:      CostModel (Time, Fuel, Wind, Wave, Current, Safety)")

    wind_prov = OpenMeteoWindProvider(timeout=30.0)
    composite_provider = CompositeEnvironmentalProvider(wind_provider=wind_prov)
    service = RoutePlanningService(
        environment_provider=composite_provider,
        grid_resolution_deg=0.25,
    )

    # 3. Execute Route Calculation & Measure Elapsed Time
    print("\n----------------------------------------------------------------------")
    print("[3] EXECUTING LIVE BATCH PIPELINE & D* LITE PATH PLANNING")
    print("----------------------------------------------------------------------")
    print("    Fetching batch bounding-box oceanographic and atmospheric data...")

    start_time = time.perf_counter()

    try:
        result = service.plan_preview_route(
            imo_number=imo_number,
            start_lat=start_lat,
            start_lon=start_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            timestamp=utc_timestamp,
        )
        elapsed_time = time.perf_counter() - start_time
    except CopernicusAuthenticationError as auth_err:
        print("\n" + "=" * 75)
        print("   LIVE DATA FETCH FAILED — COPERNICUS AUTHENTICATION REQUIRED")
        print("=" * 75)
        print(f"    Reason:  {auth_err}")
        print("    Action:  Please run 'copernicusmarine login' in your terminal.")
        print("    Note:    Unit tests run 100% offline with zero external credentials.")
        return
    except EnvironmentUnavailableError as env_err:
        print("\n" + "=" * 75)
        print("   LIVE DATA FETCH FAILED — 503 ENVIRONMENT_UNAVAILABLE")
        print("=" * 75)
        print(f"    Reason:  {env_err}")
        print("    Note:    Mapped to HTTP 503 status per docs/API_CONTRACT.md.")
        return
    except RouteNotFoundError as route_err:
        print("\n" + "=" * 75)
        print("   ROUTE PLANNING FAILED — 404 ROUTE_NOT_FOUND")
        print("=" * 75)
        print(f"    Reason:  {route_err}")
        return
    except APIException as api_err:
        print(f"\n[!] API Error [{api_err.code}]: {api_err.message}")
        return

    # 4. Format Contract-Compliant API Response
    api_response = RoutePreviewResponse(
        imo_number=result.imo_number,
        status=result.status,
        route=[Coordinate(latitude=lat, longitude=lon) for lat, lon in result.route],
        distance_nm=result.distance_nm,
        estimated_time_hours=result.estimated_time_hours,
        total_cost=result.total_cost,
    )

    # 5. Display Voyage Metrics & Waypoints
    print(f"\n    [+] Route Planning Completed in {elapsed_time:.2f} seconds.")
    print("\n----------------------------------------------------------------------")
    print("[4] OPTIMAL ROUTE METRICS & D* LITE WAYPOINTS")
    print("----------------------------------------------------------------------")
    print(f"    Route Status:         {api_response.status.upper()}")
    print(f"    Total Waypoints:      {len(api_response.route)}")
    print(f"    Total Distance:       {api_response.distance_nm:.2f} NM")
    print(f"    Estimated Transit:    {api_response.estimated_time_hours:.2f} hours (~{api_response.estimated_time_hours / 24.0:.2f} days)")
    print(f"    Total Voyage Cost:    {api_response.total_cost:.4f}")

    print("\n    Waypoints Sequence:")
    for idx, wp in enumerate(api_response.route):
        print(f"      [{idx + 1:02d}] Latitude: {wp.latitude:7.4f}°N, Longitude: {wp.longitude:7.4f}°E")

    # 6. Display JSON Response Payload
    print("\n----------------------------------------------------------------------")
    print("[5] CONTRACT-COMPLIANT API JSON RESPONSE (docs/API_CONTRACT.md)")
    print("----------------------------------------------------------------------")
    json_output = json.dumps(api_response.model_dump(), indent=2)
    print(json_output)

    print("\n" + "=" * 75)
    print("   LIVE API ROUTE DEMO COMPLETED SUCCESSFULLY [PASSED] [OK]")
    print("=" * 75)


if __name__ == "__main__":
    run_live_api_route_demo()
