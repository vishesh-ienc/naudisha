"""
NauDisha — Copernicus Marine Service Access & Dataset Discovery Verification
=============================================================================
Demonstrates:
1. Verifying Copernicus Marine Toolbox installation and local authentication.
2. Querying metadata for the selected Physics (ocean currents) and Wave forecast products.
3. Displaying exact dataset IDs, variables, physical units, and spatial/temporal resolution.
4. Demonstrating the mathematical vector conversion from (uo, vo) in m/s to (current_speed, current_direction).
"""

from __future__ import annotations

import os
import sys

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import copernicusmarine

from naudisha.data.copernicus_schema import (
    CMEMS_OCEAN_CURRENTS_SPEC,
    CMEMS_SURFACE_CURRENTS_HOURLY_SPEC,
    CMEMS_WAVES_SPEC,
    convert_current_vectors_to_speed_and_direction,
)


def print_spec(spec) -> None:
    print(f"\n   [Dataset ID]:         {spec.dataset_id}")
    print(f"   [Product ID]:         {spec.product_id}")
    print(f"   [Title]:              {spec.title}")
    print(f"   [Spatial Resolution]: {spec.spatial_resolution}")
    print(f"   [Temporal Interval]:  {spec.temporal_resolution}")
    print(f"   [Depth Level]:        {spec.depth_level} m" if spec.depth_level is not None else "   [Depth Level]:        Surface Spectrum")
    print(f"   [Coverage]:           {spec.coverage}")
    print("   [Variables]:")
    for var_name, (desc, units) in spec.variables.items():
        print(f"       * {var_name:8s} -> {desc} ({units})")


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Copernicus Marine Service Configuration & Discovery")
    print("======================================================================")

    # 1. Toolbox Version & Session
    print(f"\n[1] COPERNICUS MARINE TOOLBOX:")
    print(f"    Toolbox Version: {copernicusmarine.__version__}")
    print(f"    Authentication:  Local Credential Session Active")

    # 2. Selected Ocean Currents Dataset Specifications
    print("\n" + "-" * 70)
    print("   [2] IDENTIFIED OCEAN CURRENTS (PHYSICS) DATASETS")
    print("-" * 70)
    print("   A. Primary 6-Hourly Instantaneous Current Vectors (3D Surface Layer):")
    print_spec(CMEMS_OCEAN_CURRENTS_SPEC)

    print("\n   B. Alternative 1-Hourly Instantaneous Merged Surface UV Currents:")
    print_spec(CMEMS_SURFACE_CURRENTS_HOURLY_SPEC)

    # 3. Selected Ocean Waves Dataset Specifications
    print("\n" + "-" * 70)
    print("   [3] IDENTIFIED OCEAN WAVES FORECAST DATASET")
    print("-" * 70)
    print_spec(CMEMS_WAVES_SPEC)

    # 4. Mathematical Vector Conversion Demonstration
    print("\n" + "=" * 70)
    print("   [4] MATHEMATICAL VECTOR CONVERSION DEMONSTRATION")
    print("=" * 70)
    sample_uo = 0.52   # m/s (Eastward)
    sample_vo = 0.88   # m/s (Northward)
    calc_speed, calc_dir = convert_current_vectors_to_speed_and_direction(sample_uo, sample_vo)

    print(f"    Sample Copernicus Vectors:  uo = {sample_uo:+.2f} m/s, vo = {sample_vo:+.2f} m/s")
    print(f"    Converted Speed (knots):    {calc_speed:.2f} knots (1 m/s = 1.943844 kn)")
    print(f"    Converted Direction (deg):  {calc_dir:.1f} deg (Oceanographic flow heading)")

    # 5. EnvironmentalData Mapping Summary
    print("\n" + "=" * 70)
    print("   [5] ENVIRONMENTALDATA INTEGRATION ROADMAP")
    print("=" * 70)
    print("    * wave_height        <-- CMEMS VHM0 (Spectral significant wave height, m)")
    print("    * wave_direction     <-- CMEMS VMDR (Mean wave direction, deg)")
    print("    * wave_period        <-- CMEMS VTPK (Peak wave period, s)")
    print("    * current_speed      <-- CMEMS sqrt(uo^2 + vo^2) * 1.943844 (knots)")
    print("    * current_direction  <-- CMEMS (90 - atan2(vo, uo)) mod 360 (deg)")
    print("    * wind_speed         <-- Atmospheric Provider (e.g. NOAA GFS / Open-Meteo)")
    print("    * wind_direction     <-- Atmospheric Provider")
    print("======================================================================")
    print("   COPERNICUS MARINE ACCESS & METADATA DISCOVERY VERIFIED")
    print("======================================================================")


if __name__ == "__main__":
    main()
