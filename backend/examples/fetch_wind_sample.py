"""
NauDisha — Open-Meteo Atmospheric Wind Provider Live Sample Fetch
==================================================================
Demonstrates:
1. Connecting to the live Open-Meteo atmospheric forecast API (zero API key required).
2. Requesting 10m surface wind parameters for an Arabian Sea coordinate (18.50°N, 72.00°E).
3. Parsing wind speed (knots) and wind direction (degrees).
4. Mapping the atmospheric parameters into NauDisha's EnvironmentalData model.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.data.wind_provider import (
    OpenMeteoWindProvider,
    WindProviderError,
    WindNetworkError,
    WindDataUnavailableError,
)


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Open-Meteo Atmospheric Wind Live Sample Fetch")
    print("======================================================================")

    target_lat = 18.50  # Off Mumbai / Eastern Arabian Sea
    target_lon = 72.00
    target_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")

    print(f"\n[1] TARGET QUERY PARAMETERS:")
    print(f"    Location:   ({target_lat:.2f}N, {target_lon:.2f}E)")
    print(f"    Timestamp:  {target_time}")

    print(f"\n[2] INITIALIZING OPEN-METEO WIND PROVIDER...")
    provider = OpenMeteoWindProvider()

    print(f"\n[3] FETCHING LIVE ATMOSPHERIC WIND DATA...")
    try:
        env = provider.fetch_conditions(lat=target_lat, lon=target_lon, timestamp=target_time)

        print("\n" + "=" * 70)
        print("   [4] LIVE WIND DATA RETURNED FROM OPEN-METEO")
        print("=" * 70)
        print(f"    Timestamp:       {env.timestamp}")
        print(f"    Wind Speed:      {env.wind_speed:.2f} knots (10m surface)")
        print(f"    Wind Direction:  {env.wind_direction:.1f} deg (Direction wind arrives from)")
        print(f"    Wave Height:     {env.wave_height} (Sourced from Copernicus Marine)")
        print(f"    Current Speed:   {env.current_speed} (Sourced from Copernicus Marine)")
        print("=" * 70)
        print("   OPEN-METEO LIVE WIND FETCH COMPLETED SUCCESSFULLY")
        print("======================================================================")

    except WindNetworkError as net_err:
        print(f"\n[!] NETWORK ERROR: {net_err}")
    except WindDataUnavailableError as data_err:
        print(f"\n[!] DATA UNAVAILABLE: {data_err}")
    except WindProviderError as prov_err:
        print(f"\n[!] PROVIDER ERROR: {prov_err}")
    except Exception as exc:
        print(f"\n[!] UNEXPECTED ERROR: {exc}")


if __name__ == "__main__":
    main()
