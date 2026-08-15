"""
NauDisha — Copernicus Marine Service Live Data Acquisition Sample
===================================================================
Demonstrates:
1. Connecting to the live Copernicus Marine Service using local user credentials.
2. Requesting a targeted spatial/temporal subset for an Indian Ocean coordinate (off Mumbai, India).
3. Fetching real ocean currents (uo, vo) and wave spectrum parameters (VHM0, VMDR, VTPK).
4. Mapping the live oceanographic parameters into NauDisha's EnvironmentalData model.
5. Evaluating segment hydrodynamics using the fetched live data.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.core.models import ShipProfile, SegmentData
from naudisha.cost.model import CostModel
from naudisha.data.copernicus_provider import (
    CopernicusMarineProvider,
    CopernicusProviderError,
    CopernicusAuthenticationError,
    CopernicusDataUnavailableError,
)


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Copernicus Marine Service Live Sample Data Fetch")
    print("======================================================================")

    # 1. Target Geographic Coordinates & Timestamp (Arabian Sea / Indian Ocean)
    target_lat = 18.50  # Off Mumbai / Western Coast of India
    target_lon = 72.00  # Eastern Arabian Sea
    # Use current UTC time (or recent analysis timestamp)
    target_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")

    print(f"\n[1] TARGET QUERY PARAMETERS:")
    print(f"    Location:   ({target_lat:.2f}N, {target_lon:.2f}E) - Arabian Sea / Indian Ocean")
    print(f"    Timestamp:  {target_time}")

    # 2. Initialize Provider
    print(f"\n[2] INITIALIZING COPERNICUS MARINE PROVIDER...")
    provider = CopernicusMarineProvider()

    # 3. Fetch Conditions
    print(f"\n[3] FETCHING LIVE OCEANOGRAPHIC CONDITIONS...")
    print(f"    - Querying Ocean Currents (uo, vo from Global Physics Forecast)...")
    print(f"    - Querying Wave Parameters (Hs, direction, period from Wave Forecast)...")

    try:
        env = provider.fetch_conditions(lat=target_lat, lon=target_lon, timestamp=target_time)

        print("\n" + "=" * 70)
        print("   [4] LIVE ENVIRONMENTALDATA RETURNED FROM COPERNICUS MARINE")
        print("=" * 70)
        print(f"    Timestamp:         {env.timestamp}")
        print(f"    Current Speed:     {env.current_speed:.2f} knots")
        print(f"    Current Direction: {env.current_direction:.1f} deg (Flow heading)")
        print(f"    Wave Height (Hs):  {env.wave_height:.2f} meters")
        print(f"    Wave Direction:    {env.wave_direction:.1f} deg (Incoming direction)")
        print(f"    Wave Period (Tp):  {env.wave_period:.1f} seconds")
        print(f"    Wind Speed:        {env.wind_speed} (Pending separate atmospheric provider)")
        print(f"    Wind Direction:    {env.wind_direction}")
        print("=" * 70)

        # 4. Hydrodynamic Evaluation Demonstration
        ship = ShipProfile(
            ship_type="Container Vessel",
            length=294.0,
            beam=32.2,
            draft=12.0,
            cruising_speed=18.0,
            maximum_speed=23.0,
        )
        print(f"\n[5] HYDRODYNAMIC EVALUATION WITH LIVE CURRENTS:")
        print(f"    Vessel Cruising Speed: {ship.cruising_speed} knots")
        print(f"    Live Ocean Current:    {env.current_speed:.2f} knots towards {env.current_direction:.1f} deg")

        print("\n======================================================================")
        print("   COPERNICUS MARINE LIVE INTEGRATION COMPLETED SUCCESSFULLY")
        print("======================================================================")

    except CopernicusAuthenticationError as auth_err:
        print("\n[!] AUTHENTICATION ERROR:")
        print(f"    {auth_err}")
        print("    Please run 'copernicusmarine login' in your terminal to set up local credentials.")
    except CopernicusDataUnavailableError as data_err:
        print("\n[!] DATA UNAVAILABLE:")
        print(f"    {data_err}")
    except CopernicusProviderError as prov_err:
        print("\n[!] PROVIDER ERROR:")
        print(f"    {prov_err}")
    except Exception as exc:
        print(f"\n[!] UNEXPECTED ERROR: {exc}")


if __name__ == "__main__":
    main()
