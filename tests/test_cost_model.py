"""
Unit tests for CostModel:
- weighted cost formula accuracy
- non-navigable segment handling (infinite cost)
- extreme weather non-navigability
- custom weight adjustments
"""

import math
import unittest

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    SegmentScores,
)
from naudisha.cost.model import CostModel


class TestCostModel(unittest.TestCase):
    """Test suite for CostModel orchestrator."""

    def setUp(self):
        self.ship = ShipProfile(
            ship_type="Oil Tanker",
            length=250.0,
            beam=44.0,
            draft=14.0,
            cruising_speed=14.0,
            maximum_speed=17.0,
        )
        self.env = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=15.0,
            wind_direction=45.0,
            wave_height=2.0,
            wave_direction=45.0,
            wave_period=7.0,
            current_speed=1.5,
            current_direction=45.0,
        )
        self.segment = SegmentData(
            start_lat=15.0,
            start_lon=70.0,
            end_lat=16.0,
            end_lon=71.0,
            is_navigable=True,
        )

    def test_weighted_cost_formula(self):
        """CostModel correctly computes linear combination of scores and weights."""
        model = CostModel()
        scores = SegmentScores(
            time_score=0.2,
            fuel_score=0.3,
            wind_score=0.4,
            wave_score=0.5,
            current_score=0.1,
            safety_score=0.2,
        )
        weights = CostWeights(
            time=2.0,
            fuel=1.5,
            wind=1.0,
            wave=1.0,
            current=0.5,
            safety=3.0,
        )
        # Expected:
        # 2.0 * 0.2 = 0.4
        # 1.5 * 0.3 = 0.45
        # 1.0 * 0.4 = 0.4
        # 1.0 * 0.5 = 0.5
        # 0.5 * 0.1 = 0.05
        # 3.0 * 0.2 = 0.6
        # Total = 0.4 + 0.45 + 0.4 + 0.5 + 0.05 + 0.6 = 2.40
        total_cost = model.calculate_total_cost(scores=scores, weights=weights, is_navigable=True)
        self.assertAlmostEqual(total_cost, 2.40, places=4)

    def test_non_navigable_segment_flag(self):
        """Non-navigable segment returns math.inf."""
        model = CostModel()
        non_nav_segment = SegmentData(
            start_lat=15.0,
            start_lon=70.0,
            end_lat=16.0,
            end_lon=71.0,
            is_navigable=False,  # Land or shallow zone
        )
        eval_result = model.evaluate_segment(
            segment=non_nav_segment,
            ship=self.ship,
            env=self.env,
        )
        self.assertTrue(math.isinf(eval_result.total_cost))
        self.assertFalse(eval_result.is_navigable)

    def test_extreme_weather_non_navigable(self):
        """Conditions exceeding vessel safety limits are marked non-navigable with infinite cost."""
        model = CostModel()
        dangerous_env = EnvironmentalData(
            timestamp="2026-08-16T12:00:00Z",
            wind_speed=75.0,  # Exceeds default safety_max_wind_speed = 60.0
            wind_direction=45.0,
            wave_height=14.0, # Exceeds default safety_max_wave_height = 10.0
            wave_direction=45.0,
            wave_period=15.0,
            current_speed=4.0,
            current_direction=45.0,
        )
        eval_result = model.evaluate_segment(
            segment=self.segment,
            ship=self.ship,
            env=dangerous_env,
        )
        self.assertTrue(math.isinf(eval_result.total_cost))
        self.assertFalse(eval_result.is_navigable)

    def test_evaluate_segment_success(self):
        """Complete evaluation of navigable segment produces finite cost and valid sub-scores."""
        model = CostModel()
        eval_result = model.evaluate_segment(
            segment=self.segment,
            ship=self.ship,
            env=self.env,
        )
        self.assertTrue(eval_result.is_navigable)
        self.assertFalse(math.isinf(eval_result.total_cost))
        self.assertGreater(eval_result.total_cost, 0.0)

        # Check all scores are clamped within [0, 1]
        for score_val in (
            eval_result.scores.time_score,
            eval_result.scores.fuel_score,
            eval_result.scores.wind_score,
            eval_result.scores.wave_score,
            eval_result.scores.current_score,
            eval_result.scores.safety_score,
        ):
            self.assertGreaterEqual(score_val, 0.0)
            self.assertLessEqual(score_val, 1.0)


if __name__ == "__main__":
    unittest.main()
