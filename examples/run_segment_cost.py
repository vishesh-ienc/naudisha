"""
NauDisha — Segment Cost Model Demonstration
============================================
This example demonstrates:
1. Creating a vessel profile (ShipProfile)
2. Defining dynamic environmental conditions (EnvironmentalData)
3. Defining a geographic navigation segment (SegmentData)
4. Configuring multi-factor objective weights (CostWeights)
5. Computing derived nautical metrics, individual normalized scores [0, 1], and final weighted cost.
"""

from __future__ import annotations

import os
import sys

# Ensure package root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    CostModel,
)


def main() -> None:
    print("======================================================================")
    print("   NauDisha - Dynamic & Optimal Ship Routing System")
    print("   Cost Model Demonstration")
    print("======================================================================")

    # 1. Create Ship Profile (Container vessel)
    ship = ShipProfile(
        ship_type="Container Ship (Post-Panamax)",
        length=334.0,       # meters
        beam=42.8,          # meters
        draft=14.5,         # meters
        cruising_speed=18.0, # knots
        maximum_speed=23.0, # knots
    )
    print("\n[1] SHIP PROFILE:")
    print(f"    Type:            {ship.ship_type}")
    print(f"    Dimensions:      {ship.length}m (L) x {ship.beam}m (B) x {ship.draft}m (D)")
    print(f"    Cruising Speed:  {ship.cruising_speed} knots")
    print(f"    Max Speed:       {ship.maximum_speed} knots")

    # 2. Define Dynamic Environmental Conditions (Arabian Sea transit)
    env = EnvironmentalData(
        timestamp="2026-08-16T12:00:00Z",
        wind_speed=22.0,      # knots
        wind_direction=240.0, # degrees (from SW)
        wave_height=2.8,      # meters (moderate rough sea)
        wave_direction=235.0, # degrees
        wave_period=8.5,      # seconds
        current_speed=1.8,    # knots
        current_direction=60.0, # degrees (flowing towards NE)
    )
    print("\n[2] ENVIRONMENTAL CONDITIONS:")
    print(f"    Timestamp:       {env.timestamp}")
    print(f"    Wind:            {env.wind_speed} knots from {env.wind_direction} deg")
    print(f"    Waves:           {env.wave_height}m (Period: {env.wave_period}s, Dir: {env.wave_direction} deg)")
    print(f"    Ocean Current:   {env.current_speed} knots towards {env.current_direction} deg")

    # 3. Create Navigational Segment (e.g. Mumbai offing to Gujarat coast)
    segment = SegmentData(
        start_lat=18.9220,
        start_lon=72.8347,
        end_lat=20.0000,
        end_lon=71.5000,
        is_navigable=True,
    )
    print("\n[3] NAVIGATIONAL SEGMENT:")
    print(f"    Start Waypoint:  ({segment.start_lat:.4f} N, {segment.start_lon:.4f} E)")
    print(f"    End Waypoint:    ({segment.end_lat:.4f} N, {segment.end_lon:.4f} E)")
    print(f"    Navigable:       {segment.is_navigable}")

    # 4. Configure Optimization Weights
    weights = CostWeights(
        time=1.5,      # Priority on transit time
        fuel=1.2,      # Priority on fuel economy
        wind=1.0,      # Aerodynamic drag factor
        wave=1.0,      # Sea-keeping & motion factor
        current=0.8,   # Current drift factor
        safety=2.0,    # High safety weighting
    )
    print("\n[4] COST WEIGHTS:")
    print(f"    Time: {weights.time}, Fuel: {weights.fuel}, Wind: {weights.wind}, "
          f"Wave: {weights.wave}, Current: {weights.current}, Safety: {weights.safety}")

    # 5. Evaluate Segment with CostModel
    cost_model = CostModel()
    evaluation = cost_model.evaluate_segment(
        segment=segment,
        ship=ship,
        env=env,
        weights=weights,
    )

    metrics = evaluation.metrics
    scores = evaluation.scores

    print("\n" + "-" * 70)
    print("   DERIVED HYDRODYNAMIC & NAUTICAL METRICS")
    print("-" * 70)
    print(f"    Great-Circle Distance:    {metrics.distance_nm:.2f} NM ({metrics.distance_km:.2f} km)")
    print(f"    True Bearing:             {metrics.bearing:.2f} deg")
    print(f"    Relative Wind Angle:      {metrics.relative_wind_dir:.2f} deg (0 deg=headwind, 180 deg=tailwind)")
    print(f"    Relative Current Angle:   {metrics.relative_current_dir:.2f} deg (0 deg=following, 180 deg=opposing)")
    print(f"    Along-Track Current:      {metrics.along_track_current:+.2f} knots ({'Assisting' if metrics.along_track_current > 0 else 'Opposing'})")
    print(f"    Effective Speed (SOG):    {metrics.effective_speed:.2f} knots")
    print(f"    Estimated Travel Time:    {metrics.travel_time_hours:.2f} hours")

    print("\n" + "-" * 70)
    print("   MODULAR COMPONENT SCORES (0.0 = Best, 1.0 = Worst)")
    print("-" * 70)
    print(f"    Time Score:       {scores.time_score:.4f}")
    print(f"    Fuel Score:       {scores.fuel_score:.4f}")
    print(f"    Wind Score:       {scores.wind_score:.4f}")
    print(f"    Wave Score:       {scores.wave_score:.4f}")
    print(f"    Current Score:    {scores.current_score:.4f}")
    print(f"    Safety Score:     {scores.safety_score:.4f}")

    print("\n" + "=" * 70)
    print(f"   FINAL WEIGHTED SEGMENT COST: {evaluation.total_cost:.4f}")
    print(f"   SEGMENT STATUS:             {'NAVIGABLE (SAFE)' if evaluation.is_navigable else 'NON-NAVIGABLE'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
