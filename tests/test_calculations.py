"""
Unit tests for nautical and hydrodynamic derived calculations:
- distance (Haversine)
- bearing (Great circle azimuth)
- relative direction
- favorable current
- opposing current
- effective speed
- travel time
"""

import math
import unittest

from naudisha.core.calculations import (
    calculate_haversine_distance,
    calculate_bearing,
    calculate_relative_direction,
    calculate_along_track_current,
    calculate_effective_speed,
    calculate_travel_time,
    calculate_derived_metrics,
    EARTH_RADIUS_NM,
    KM_PER_NAUTICAL_MILE,
)
from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    ScoringConfig,
)


class TestCalculations(unittest.TestCase):
    """Test suite for derived calculations."""

    def test_distance_zero(self):
        """Zero distance when start and end coordinates are identical."""
        dist = calculate_haversine_distance(18.9220, 72.8347, 18.9220, 72.8347, unit="nm")
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_distance_known_meridian(self):
        """Distance along prime meridian 1 degree latitude should equal approx 60 NM."""
        # 1 degree of latitude = 60 nautical miles
        dist_nm = calculate_haversine_distance(0.0, 0.0, 1.0, 0.0, unit="nm")
        self.assertAlmostEqual(dist_nm, 60.0, delta=0.5)

        # In km
        dist_km = calculate_haversine_distance(0.0, 0.0, 1.0, 0.0, unit="km")
        self.assertAlmostEqual(dist_km, 60.0 * KM_PER_NAUTICAL_MILE, delta=1.0)

    def test_bearing_cardinal_directions(self):
        """Bearing calculations for standard cardinal directions."""
        # Due North
        b_north = calculate_bearing(0.0, 0.0, 10.0, 0.0)
        self.assertAlmostEqual(b_north, 0.0, places=2)

        # Due East
        b_east = calculate_bearing(0.0, 0.0, 0.0, 10.0)
        self.assertAlmostEqual(b_east, 90.0, places=2)

        # Due South
        b_south = calculate_bearing(10.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(b_south, 180.0, places=2)

        # Due West
        b_west = calculate_bearing(0.0, 10.0, 0.0, 0.0)
        self.assertAlmostEqual(b_west, 270.0, places=2)

    def test_relative_direction(self):
        """Relative angular difference between headings."""
        # Same direction -> 0 degrees
        self.assertAlmostEqual(calculate_relative_direction(90.0, 90.0), 0.0)

        # Opposite direction -> 180 degrees
        self.assertAlmostEqual(calculate_relative_direction(0.0, 180.0), 180.0)

        # Wrap around 360/0 border (350 deg vs 10 deg -> 20 deg diff)
        self.assertAlmostEqual(calculate_relative_direction(350.0, 10.0), 20.0)
        self.assertAlmostEqual(calculate_relative_direction(10.0, 350.0), 20.0)

        # Orthogonal -> 90 degrees
        self.assertAlmostEqual(calculate_relative_direction(45.0, 135.0), 90.0)

    def test_favorable_current(self):
        """Positive along-track current when current flows in same direction as ship heading."""
        # Ship heading North (0°), Current flowing North (0°) at 3.0 knots
        along_track = calculate_along_track_current(
            current_speed=3.0,
            current_direction=0.0,
            ship_bearing=0.0,
        )
        self.assertAlmostEqual(along_track, 3.0, places=4)
        self.assertGreater(along_track, 0.0)

        # Ship heading East (90°), Current flowing East (90°) at 2.5 knots
        along_track_east = calculate_along_track_current(
            current_speed=2.5,
            current_direction=90.0,
            ship_bearing=90.0,
        )
        self.assertAlmostEqual(along_track_east, 2.5, places=4)

    def test_opposing_current(self):
        """Negative along-track current when current flows in opposite direction of ship heading."""
        # Ship heading North (0°), Current flowing South (180°) at 3.0 knots
        along_track = calculate_along_track_current(
            current_speed=3.0,
            current_direction=180.0,
            ship_bearing=0.0,
        )
        self.assertAlmostEqual(along_track, -3.0, places=4)
        self.assertLess(along_track, 0.0)

        # Perpendicular current -> 0 along-track
        along_track_cross = calculate_along_track_current(
            current_speed=2.0,
            current_direction=90.0,
            ship_bearing=0.0,
        )
        self.assertAlmostEqual(along_track_cross, 0.0, places=4)

    def test_effective_speed(self):
        """Effective speed increases with favorable current and decreases with opposing current."""
        cruising = 14.0
        max_speed = 18.0

        # Favorable current +2 knots -> 16 knots
        speed_fav = calculate_effective_speed(
            cruising_speed=cruising,
            along_track_current=2.0,
            maximum_speed=max_speed,
        )
        self.assertAlmostEqual(speed_fav, 16.0)

        # Opposing current -3 knots -> 11 knots
        speed_opp = calculate_effective_speed(
            cruising_speed=cruising,
            along_track_current=-3.0,
            maximum_speed=max_speed,
        )
        self.assertAlmostEqual(speed_opp, 11.0)

        # Clamp at max speed
        speed_clamped_max = calculate_effective_speed(
            cruising_speed=cruising,
            along_track_current=10.0,
            maximum_speed=max_speed,
        )
        self.assertAlmostEqual(speed_clamped_max, max_speed)

        # Clamp at min allowed speed
        speed_clamped_min = calculate_effective_speed(
            cruising_speed=cruising,
            along_track_current=-20.0,
            maximum_speed=max_speed,
            min_allowed_speed=0.5,
        )
        self.assertAlmostEqual(speed_clamped_min, 0.5)

    def test_travel_time(self):
        """Travel time calculation: distance / speed."""
        # 120 NM at 15 knots = 8.0 hours
        time_hours = calculate_travel_time(distance_nm=120.0, effective_speed_knots=15.0)
        self.assertAlmostEqual(time_hours, 8.0)

        # Zero or negative speed raises ValueError
        with self.assertRaises(ValueError):
            calculate_travel_time(distance_nm=100.0, effective_speed_knots=0.0)
        with self.assertRaises(ValueError):
            calculate_travel_time(distance_nm=100.0, effective_speed_knots=-2.0)

    def test_calculate_derived_metrics_integration(self):
        """Integration test for calculate_derived_metrics."""
        ship = ShipProfile(
            ship_type="Container",
            length=300.0,
            beam=40.0,
            draft=12.0,
            cruising_speed=15.0,
            maximum_speed=20.0,
        )
        env = EnvironmentalData(
            timestamp="2026-08-16T00:00:00Z",
            wind_speed=20.0,
            wind_direction=0.0,     # Wind from North
            wave_height=2.5,
            wave_direction=0.0,
            wave_period=8.0,
            current_speed=2.0,
            current_direction=0.0,  # Current flowing North
        )
        segment = SegmentData(start_lat=10.0, start_lon=70.0, end_lat=11.0, end_lon=70.0)  # Navigating North (0°)

        metrics = calculate_derived_metrics(segment=segment, ship=ship, env=env)
        self.assertAlmostEqual(metrics.bearing, 0.0, delta=0.5)
        self.assertAlmostEqual(metrics.relative_wind_dir, 0.0, delta=0.5)  # Headwind
        self.assertAlmostEqual(metrics.relative_current_dir, 0.0, delta=0.5)
        self.assertAlmostEqual(metrics.along_track_current, 2.0, delta=0.1)  # Favorable
        self.assertAlmostEqual(metrics.effective_speed, 17.0, delta=0.1)     # 15 + 2
        self.assertGreater(metrics.travel_time_hours, 0.0)


if __name__ == "__main__":
    unittest.main()
