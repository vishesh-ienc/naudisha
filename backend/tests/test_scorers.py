"""
Unit tests for modular scoring functions:
- time_score
- fuel_score
- wind_score
- wave_score
- current_score
- safety_score
"""

import unittest

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    DerivedSegmentMetrics,
    ScoringConfig,
)
from naudisha.cost.scorers import (
    calculate_time_score,
    calculate_fuel_score,
    calculate_wind_score,
    calculate_wave_score,
    calculate_current_score,
    calculate_safety_score,
    evaluate_all_scores,
)


class TestScorers(unittest.TestCase):
    """Test suite for individual score functions."""

    def setUp(self):
        self.ship = ShipProfile(
            ship_type="Cargo",
            length=200.0,
            beam=32.0,
            draft=10.0,
            cruising_speed=15.0,
            maximum_speed=20.0,
        )
        self.config = ScoringConfig(
            min_travel_time_factor=0.8,
            max_travel_time_factor=2.0,
            max_reference_wind_speed=50.0,
            max_reference_wave_height=8.0,
            max_reference_current_speed=4.0,
            safety_max_wave_height=10.0,
            safety_max_wind_speed=60.0,
        )

    def test_time_score(self):
        """Faster travel time yields lower cost score (towards 0)."""
        dist_nm = 150.0
        # Baseline calm time = 150 / 15 = 10.0 hours
        # Fast trip: 8.0 hours -> min_time_ref = 8.0 -> score = 0.0
        score_fast = calculate_time_score(
            travel_time_hours=8.0,
            distance_nm=dist_nm,
            cruising_speed=15.0,
            config=self.config,
        )
        self.assertAlmostEqual(score_fast, 0.0, places=2)

        # Slow delayed trip: 20.0 hours -> max_time_ref = 20.0 -> score = 1.0
        score_slow = calculate_time_score(
            travel_time_hours=20.0,
            distance_nm=dist_nm,
            cruising_speed=15.0,
            config=self.config,
        )
        self.assertAlmostEqual(score_slow, 1.0, places=2)

        # In-between: 14.0 hours -> (14 - 8) / (20 - 8) = 6/12 = 0.5
        score_mid = calculate_time_score(
            travel_time_hours=14.0,
            distance_nm=dist_nm,
            cruising_speed=15.0,
            config=self.config,
        )
        self.assertAlmostEqual(score_mid, 0.5, places=2)

    def test_fuel_score(self):
        """Assisted speed yields lower fuel score; slowed speed yields higher fuel score."""
        # High effective speed (assisted)
        metrics_fast = DerivedSegmentMetrics(
            distance_nm=100.0,
            distance_km=185.2,
            bearing=0.0,
            relative_wind_dir=180.0,
            relative_current_dir=0.0,
            along_track_current=3.0,
            effective_speed=18.0,
            travel_time_hours=5.55,
        )
        score_fav = calculate_fuel_score(metrics=metrics_fast, ship=self.ship, config=self.config)

        # Low effective speed (opposed)
        metrics_slow = DerivedSegmentMetrics(
            distance_nm=100.0,
            distance_km=185.2,
            bearing=0.0,
            relative_wind_dir=0.0,
            relative_current_dir=180.0,
            along_track_current=-3.0,
            effective_speed=12.0,
            travel_time_hours=8.33,
        )
        score_opp = calculate_fuel_score(metrics=metrics_slow, ship=self.ship, config=self.config)

        self.assertLess(score_fav, score_opp)
        self.assertTrue(0.0 <= score_fav <= 1.0)
        self.assertTrue(0.0 <= score_opp <= 1.0)

    def test_wind_score(self):
        """Headwind yields higher penalty than tailwind."""
        wind_speed = 30.0

        # Headwind (rel wind = 0°)
        score_head = calculate_wind_score(
            wind_speed=wind_speed,
            relative_wind_dir=0.0,
            config=self.config,
        )
        # Tailwind (rel wind = 180°)
        score_tail = calculate_wind_score(
            wind_speed=wind_speed,
            relative_wind_dir=180.0,
            config=self.config,
        )
        # Crosswind (rel wind = 90°)
        score_cross = calculate_wind_score(
            wind_speed=wind_speed,
            relative_wind_dir=90.0,
            config=self.config,
        )

        self.assertAlmostEqual(score_tail, 0.0, places=2)
        self.assertAlmostEqual(score_head, 30.0 / 50.0, places=2)  # 0.6
        self.assertAlmostEqual(score_cross, 15.0 / 50.0, places=2)  # 0.3
        self.assertGreater(score_head, score_cross)
        self.assertGreater(score_cross, score_tail)

    def test_wave_score(self):
        """Higher waves yield higher score; head seas yield higher score than following seas."""
        # Calm sea
        score_calm = calculate_wave_score(
            wave_height=0.0,
            wave_direction=0.0,
            ship_bearing=0.0,
            config=self.config,
        )
        self.assertAlmostEqual(score_calm, 0.0)

        # High head sea (wave from 0°, ship bearing 0°)
        score_head = calculate_wave_score(
            wave_height=4.0,
            wave_direction=0.0,
            ship_bearing=0.0,
            config=self.config,
        )
        # High following sea (wave from 180°, ship bearing 0°)
        score_following = calculate_wave_score(
            wave_height=4.0,
            wave_direction=180.0,
            ship_bearing=0.0,
            config=self.config,
        )

        self.assertGreater(score_head, score_following)
        self.assertTrue(0.0 <= score_head <= 1.0)
        self.assertTrue(0.0 <= score_following <= 1.0)

    def test_current_score(self):
        """Favorable along-track current gives score 0.0, opposing current gives 1.0."""
        # Maximum favorable current (+4.0 knots) -> score 0.0
        score_fav = calculate_current_score(along_track_current=4.0, config=self.config)
        self.assertAlmostEqual(score_fav, 0.0, places=2)

        # Maximum opposing current (-4.0 knots) -> score 1.0
        score_opp = calculate_current_score(along_track_current=-4.0, config=self.config)
        self.assertAlmostEqual(score_opp, 1.0, places=2)

        # Zero current -> score 0.5
        score_neutral = calculate_current_score(along_track_current=0.0, config=self.config)
        self.assertAlmostEqual(score_neutral, 0.5, places=2)

    def test_safety_score(self):
        """Safety score evaluates distance to vessel operational limits."""
        # Benign conditions
        env_calm = EnvironmentalData(
            timestamp="2026-08-16T00:00:00Z",
            wind_speed=5.0,
            wind_direction=0.0,
            wave_height=0.5,
            wave_direction=0.0,
            wave_period=5.0,
            current_speed=0.5,
            current_direction=0.0,
        )
        score_safe = calculate_safety_score(ship=self.ship, env=env_calm, config=self.config)
        self.assertLess(score_safe, 0.2)

        # Severe hurricane conditions
        env_extreme = EnvironmentalData(
            timestamp="2026-08-16T00:00:00Z",
            wind_speed=60.0,
            wind_direction=0.0,
            wave_height=10.0,
            wave_direction=0.0,
            wave_period=12.0,
            current_speed=3.0,
            current_direction=0.0,
        )
        score_extreme = calculate_safety_score(ship=self.ship, env=env_extreme, config=self.config)
        self.assertAlmostEqual(score_extreme, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
