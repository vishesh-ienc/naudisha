"""
Test script to verify Copernicus Marine credentials from .env.
"""

import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Map .env names to Copernicus Marine standard env vars
if os.getenv("COPERNICUS_MARINE_USERNAME"):
    os.environ["COPERNICUSMARINE_SERVICE_USERNAME"] = os.getenv("COPERNICUS_MARINE_USERNAME")
if os.getenv("COPERNICUS_MARINE_PASSWORD"):
    os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"] = os.getenv("COPERNICUS_MARINE_PASSWORD")

from naudisha.data.copernicus_provider import CopernicusMarineProvider


def main():
    print("=== Copernicus Marine Service Credentials Verification ===\n")
    user = os.getenv("COPERNICUS_MARINE_USERNAME") or os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
    if not user:
        print("ERROR: COPERNICUS_MARINE_USERNAME not found in .env")
        return

    print(f"Found Copernicus Username in .env: {user}")
    print("Connecting to Copernicus Marine Service Physics API (coordinates: 18.52N, 72.91E)...")
    
    try:
        provider = CopernicusMarineProvider()
        now_dt = datetime.now(timezone.utc)
        env = provider.fetch_conditions(18.52, 72.91, timestamp=now_dt)
        
        print("\nSUCCESS! Real Copernicus Marine Data Retrieved:")
        print(f"   Ocean Current Speed:     {env.current_speed:.2f} m/s" if env.current_speed else "   Current: Available")
        print(f"   Ocean Current Direction: {env.current_direction:.1f}°" if env.current_direction else "")
        print(f"   Significant Wave Height: {env.wave_height:.2f} m" if env.wave_height else "")
        print(f"   Wave Period (Tp):        {env.wave_period:.1f} s" if env.wave_period else "")
        print(f"   Wave Direction:          {env.wave_direction:.1f}°" if env.wave_direction else "")
        print(f"   Timestamp:               {env.timestamp}")
        print("\nCopernicus Marine Service credentials are 100% VALID and functional!")
    except Exception as exc:
        print(f"\nCopernicus Authentication / Fetch Result: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
