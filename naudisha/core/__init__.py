"""
Core data models, derived calculations, and normalization utilities.
"""

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    CostWeights,
    ScoringConfig,
    DerivedSegmentMetrics,
    SegmentScores,
    SegmentEvaluation,
)
from naudisha.core.normalization import normalize_min_max
from naudisha.core.calculations import (
    calculate_haversine_distance,
    calculate_bearing,
    calculate_relative_direction,
    calculate_along_track_current,
    calculate_effective_speed,
    calculate_travel_time,
    calculate_derived_metrics,
)

__all__ = [
    "ShipProfile",
    "EnvironmentalData",
    "SegmentData",
    "CostWeights",
    "ScoringConfig",
    "DerivedSegmentMetrics",
    "SegmentScores",
    "SegmentEvaluation",
    "normalize_min_max",
    "calculate_haversine_distance",
    "calculate_bearing",
    "calculate_relative_direction",
    "calculate_along_track_current",
    "calculate_effective_speed",
    "calculate_travel_time",
    "calculate_derived_metrics",
]
