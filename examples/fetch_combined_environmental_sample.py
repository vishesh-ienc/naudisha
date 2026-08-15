"""
NauDisha — Unified Multi-Source Environmental Data Fusion Demo
==============================================================
Demonstrates:
1. Sourcing real ocean currents (uo, vo) and wave spectra (Hs, dir, Tp) from Copernicus Marine.
2. Sourcing real atmospheric wind velocity (speed, direction) from Open-Meteo.
3. Fusing both data streams into a single unified EnvironmentalData object.
4. Evaluating segment hydrodynamics and multi-factor cost using NauDisha's CostModel.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.core.models import ShipProfile, SegmentData, CostWeights
from naudisha.cost.model import CostModel
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.copernicus_provider import CopernicusAuthenticationError, CopernicusProviderError
from naudisha.data.wind_provider import WindProviderError


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Unified Multi-Source Environmental Data Fusion Demo")
    print("   (Copernicus Marine Currents & Waves + Open-Meteo Wind Vectors)")
    print("======================================================================")

    target_lat = 18.50  # Arabian Sea (Off Western Coast of India)
    target_lon = 72.00
    target_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")

    print(f"\n[1] VOYAGE WAYPOINT COORDINATES:")
    print(f"    Position:   ({target_lat:.2f}N, {target_lon:.2f}E)")
    print(f"    Timestamp:  {target_time}")

    print(f"\n[2] INITIALIZING COMPOSITE DATA FUSION PROVIDER...")
    composite_provider = CompositeEnvironmentalProvider()

    print(f"\n[3] FETCHING LIVE OCEANOGRAPHIC & ATMOSPHERIC CONDITIONS...")
    try:
        env = composite_provider.fetch_conditions(lat=target_lat, lon=target_lon, timestamp=target_time)

        print("\n" + "=" * 70)
        print("   [4] UNIFIED LIVE ENVIRONMENTALDATA OBJECT")
        print("=" * 70)
        print(f"    Observation Timestamp: {env.timestamp}")
        print(f"    --- Ocean Hydrodynamics (Copernicus Marine Physics) ---")
        print(f"    Current Speed:         {env.current_speed:.2f} knots")
        print(f"    Current Direction:     {env.current_direction:.1f} deg (Flow heading)")
        print(f"    --- Sea-State Spectrum (Copernicus Marine Waves) ---")
        print(f"    Significant Wave (Hs): {env.wave_height:.2f} meters")
        print(f"    Wave Direction:        {env.wave_direction:.1f} deg (Incoming)")
        print(f"    Peak Wave Period (Tp): {env.wave_period:.1f} seconds")
        print(f"    --- Atmospheric Conditions (Open-Meteo 10m Wind) ---")
        print(f"    Wind Speed:            {env.wind_speed:.2f} knots")
        print(f"    Wind Direction:        {env.wind_direction:.1f} deg (From)")
        print("=" * 70)

        # 4. Comprehensive Cost Evaluation
        ship = ShipProfile(
            ship_type="Container Vessel (Panamax)",
            length=294.0,
            beam=32.2,
            draft=12.0,
            cruising_speed=18.0,
            maximum_speed=23.0,
        )
        segment = SegmentData(
            start_lat=target_lat,
            start_lon=target_lon,
            end_lat=target_lat + 0.5,
            end_lon=target_lon + 0.5,
        )
        cost_model = CostModel(default_weights=CostWeights(time=1.5, fuel=1.2, wind=1.0, wave=1.0, current=0.8, safety=2.0))
        eval_result = cost_model.evaluate_segment(segment=segment, ship=ship, env=env)

        print(f"\n[5] LIVE SEGMENT COST EVALUATION WITH UNIFIED DATA:")
        print(f"    Segment Distance:     {eval_result.metrics.distance_nm:.2f} NM")
        print(f"    Ship Heading:         {eval_result.metrics.bearing:.1f} deg")
        print(f"    Effective Speed:      {eval_result.metrics.effective_speed:.2f} knots")
        print(f"    Estimated Time:       {eval_result.metrics.travel_time_hours:.2f} hours")
        print(f"    Time Score:           {eval_result.scores.time_score:.4f}")
        print(f"    Fuel Score:           {eval_result.scores.fuel_score:.4f}")
        print(f"    Wind Score:           {eval_result.scores.wind_score:.4f}")
        print(f"    Wave Score:           {eval_result.scores.wave_score:.4f}")
        print(f"    Current Score:        {eval_result.scores.current_score:.4f}")
        print(f"    Safety Score:         {eval_result.scores.safety_score:.4f}")
        print(f"    TOTAL SEGMENT COST:   {eval_result.total_cost:.4f}")

        print("\n======================================================================")
        print("   UNIFIED ENVIRONMENTAL DATA FUSION VERIFIED SUCCESSFULLY")
        print("======================================================================")

    except CopernicusAuthenticationError as auth_err:
        print(f"\n[!] COPERNICUS AUTHENTICATION ERROR: {auth_err}")
    except (CopernicusProviderError, WindProviderError) as prov_err:
        print(f"\n[!] PROVIDER ERROR: {prov_err}")
    except Exception as exc:
        print(f"\n[!] UNEXPECTED ERROR: {exc}")


if __name__ == "__main__":
    main()
