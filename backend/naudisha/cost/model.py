"""
Core CostModel orchestrator for NauDisha ship routing system.
Calculates multi-objective segment costs with non-navigable constraint enforcement.
"""

from __future__ import annotations

import math
from typing import Optional

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    SegmentScores,
    DerivedSegmentMetrics,
    SegmentEvaluation,
)
from naudisha.core.calculations import calculate_derived_metrics
from naudisha.cost.scorers import evaluate_all_scores


class CostModel:
    """
    Modular cost model for evaluating ship routing segments.

    Computes multi-factor weighted costs based on time, fuel, wind, wave, current, and safety factors.
    Guarantees that non-navigable segments (land, shallow drafts, extreme hazard zones) return infinite cost (math.inf).
    """

    def __init__(
        self,
        default_weights: Optional[CostWeights] = None,
        default_config: Optional[ScoringConfig] = None,
    ) -> None:
        self.weights = default_weights or CostWeights()
        self.config = default_config or ScoringConfig()

    def calculate_total_cost(
        self,
        scores: SegmentScores,
        weights: Optional[CostWeights] = None,
        is_navigable: bool = True,
    ) -> float:
        """
        Calculates the weighted linear combination of individual normalized scores.

        total_cost =
            time_weight * time_score +
            fuel_weight * fuel_score +
            wind_weight * wind_score +
            wave_weight * wave_score +
            current_weight * current_score +
            safety_weight * safety_score

        Returns:
            float: Total segment cost, or float('inf') if segment is non-navigable.
        """
        if not is_navigable:
            return math.inf

        w = weights or self.weights

        total_cost = (
            w.time * scores.time_score
            + w.fuel * scores.fuel_score
            + w.wind * scores.wind_score
            + w.wave * scores.wave_score
            + w.current * scores.current_score
            + w.safety * scores.safety_score
        )

        return float(total_cost)

    def evaluate_segment(
        self,
        segment: SegmentData,
        ship: ShipProfile,
        env: EnvironmentalData,
        weights: Optional[CostWeights] = None,
        config: Optional[ScoringConfig] = None,
    ) -> SegmentEvaluation:
        """
        Executes end-to-end evaluation for a single segment:
        1. Computes derived nautical/hydrodynamic metrics.
        2. Computes 6 modular normalized scores [0, 1].
        3. Computes weighted total cost or inf for non-navigable segments.

        Args:
            segment: Start and end coordinates, navigable status.
            ship: Static vessel characteristics.
            env: Dynamic environmental parameters.
            weights: Optional custom cost weights.
            config: Optional custom scoring configuration.

        Returns:
            SegmentEvaluation dataclass containing all intermediate metrics, scores, and total_cost.
        """
        cfg = config or self.config
        w = weights or self.weights

        # 1. Derived calculations
        metrics = calculate_derived_metrics(segment=segment, ship=ship, env=env, config=cfg)

        # 2. Check navigable constraints (segment flag + safety limits)
        is_navigable = segment.is_navigable
        if (
            env.wave_height > cfg.safety_max_wave_height
            or env.wind_speed > cfg.safety_max_wind_speed
        ):
            # Exceeds absolute vessel survival thresholds
            is_navigable = False

        # 3. Individual modular scores
        scores = evaluate_all_scores(
            segment=segment,
            ship=ship,
            env=env,
            metrics=metrics,
            config=cfg,
        )

        # 4. Total weighted cost
        total_cost = self.calculate_total_cost(
            scores=scores,
            weights=w,
            is_navigable=is_navigable,
        )

        return SegmentEvaluation(
            segment=segment,
            metrics=metrics,
            scores=scores,
            weights=w,
            total_cost=total_cost,
            is_navigable=is_navigable,
        )
