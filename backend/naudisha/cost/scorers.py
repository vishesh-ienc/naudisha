"""
Modular cost scoring functions for ship routing.
Every score outputs a normalized float in [0.0, 1.0] where 0 is best and 1 is worst.
"""

from __future__ import annotations

import math
from typing import Optional

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    DerivedSegmentMetrics,
    ScoringConfig,
    SegmentScores,
)
from naudisha.core.normalization import normalize_min_max, clamp


def calculate_time_score(
    travel_time_hours: float,
    distance_nm: float,
    cruising_speed: float,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes normalized travel time score.

    Args:
        travel_time_hours: Actual calculated travel time for the segment.
        distance_nm: Segment distance in nautical miles.
        cruising_speed: Vessel design cruising speed (knots).
        config: Scoring configuration for reference bounds.

    Returns:
        Score in [0.0, 1.0] where 0.0 = fastest / best, 1.0 = slowest / worst.
    """
    cfg = config or ScoringConfig()

    # Baseline calm-water transit time
    baseline_time = distance_nm / cruising_speed if cruising_speed > 0 else travel_time_hours
    min_time_ref = baseline_time * cfg.min_travel_time_factor
    max_time_ref = baseline_time * cfg.max_travel_time_factor

    return normalize_min_max(
        value=travel_time_hours,
        min_val=min_time_ref,
        max_val=max_time_ref,
        invert=False,
    )


def calculate_fuel_score(
    metrics: DerivedSegmentMetrics,
    ship: ShipProfile,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes modular fuel consumption proxy score.
    Reflects the engine load and speed loss caused by resistance factors.

    Args:
        metrics: Derived segment metrics including effective speed.
        ship: Vessel characteristics.
        config: Scoring configuration.

    Returns:
        Score in [0.0, 1.0] where 0.0 = minimal fuel consumption proxy, 1.0 = maximum fuel consumption proxy.
    """
    cfg = config or ScoringConfig()

    # Relative speed performance ratio: effective_speed / cruising_speed
    # High ratio (assisted by current) -> high fuel efficiency -> lower cost score
    # Low ratio (slowed down by opposition) -> low fuel efficiency -> higher cost score
    speed_ratio = metrics.effective_speed / ship.cruising_speed if ship.cruising_speed > 0 else 1.0

    # Map speed_ratio [min_factor, max_factor] to [1.0, 0.0] (invert=True)
    return normalize_min_max(
        value=speed_ratio,
        min_val=cfg.min_travel_time_factor,
        max_val=cfg.max_travel_time_factor,
        invert=True,
    )


def calculate_wind_score(
    wind_speed: float,
    relative_wind_dir: float,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes aerodynamic resistance score based on wind speed and relative heading.

    Convention:
        - relative_wind_dir: 0° is direct headwind (worst), 180° is direct tailwind (best).

    Args:
        wind_speed: Wind speed in knots.
        relative_wind_dir: Relative wind direction in degrees [0, 180].
        config: Scoring configuration.

    Returns:
        Score in [0.0, 1.0] where 0.0 = calm/tailwind, 1.0 = severe headwind.
    """
    cfg = config or ScoringConfig()

    # Direction penalty multiplier: (1 + cos(relative_wind_dir)) / 2
    # 0° (headwind) -> cos(0) = 1.0 -> multiplier = 1.0
    # 90° (crosswind) -> cos(pi/2) = 0.0 -> multiplier = 0.5
    # 180° (tailwind) -> cos(pi) = -1.0 -> multiplier = 0.0
    rad = math.radians(relative_wind_dir)
    dir_multiplier = (1.0 + math.cos(rad)) / 2.0

    raw_wind_impact = wind_speed * dir_multiplier
    return normalize_min_max(
        value=raw_wind_impact,
        min_val=0.0,
        max_val=cfg.max_reference_wind_speed,
        invert=False,
    )


def calculate_wave_score(
    wave_height: float,
    wave_direction: float,
    ship_bearing: float,
    wave_period: float = 0.0,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes sea-state wave impact score based on wave height and wave encounter angle.

    Args:
        wave_height: Significant wave height (Hs) in meters.
        wave_direction: Wave propagation direction in degrees [0, 360).
        ship_bearing: Ship navigational heading in degrees [0, 360).
        wave_period: Wave peak period in seconds.
        config: Scoring configuration.

    Returns:
        Score in [0.0, 1.0] where 0.0 = calm sea, 1.0 = severe sea state.
    """
    cfg = config or ScoringConfig()

    # Direction encounter factor
    angle_diff = abs(ship_bearing - wave_direction) % 360.0
    if angle_diff > 180.0:
        angle_diff = 360.0 - angle_diff

    # Head and beam seas induce more added resistance than following seas
    dir_multiplier = (1.0 + math.cos(math.radians(angle_diff))) / 2.0

    raw_wave_impact = wave_height * (0.5 + 0.5 * dir_multiplier)
    return normalize_min_max(
        value=raw_wave_impact,
        min_val=0.0,
        max_val=cfg.max_reference_wave_height,
        invert=False,
    )


def calculate_current_score(
    along_track_current: float,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes hydrodynamic current cost score based on along-track velocity component.

    Convention:
        - Favorable current (positive along-track) maps towards 0.0 (best).
        - Opposing current (negative along-track) maps towards 1.0 (worst).

    Args:
        along_track_current: Current velocity along the track in knots.
        config: Scoring configuration.

    Returns:
        Score in [0.0, 1.0] where 0.0 = maximum favorable current, 1.0 = maximum opposing current.
    """
    cfg = config or ScoringConfig()
    max_ref = cfg.max_reference_current_speed

    # along_track_current ranges from -max_ref (worst) to +max_ref (best)
    # Using invert=True ensures +max_ref -> 0.0 and -max_ref -> 1.0
    return normalize_min_max(
        value=along_track_current,
        min_val=-max_ref,
        max_val=max_ref,
        invert=True,
    )


def calculate_safety_score(
    ship: ShipProfile,
    env: EnvironmentalData,
    config: Optional[ScoringConfig] = None,
) -> float:
    """
    Computes environmental safety penalty score relative to vessel operational limits.

    Args:
        ship: Vessel dimensions and limits.
        env: Environmental conditions.
        config: Scoring configuration.

    Returns:
        Score in [0.0, 1.0] where 0.0 = benign safe conditions, 1.0 = hazardous conditions.
    """
    cfg = config or ScoringConfig()

    wave_hazard = normalize_min_max(
        value=env.wave_height,
        min_val=0.0,
        max_val=cfg.safety_max_wave_height,
        invert=False,
    )
    wind_hazard = normalize_min_max(
        value=env.wind_speed,
        min_val=0.0,
        max_val=cfg.safety_max_wind_speed,
        invert=False,
    )

    # Combined environmental hazard score (taking max or weighted envelope)
    safety_score = max(wave_hazard, wind_hazard)
    return clamp(safety_score, 0.0, 1.0)


def evaluate_all_scores(
    segment: SegmentData,
    ship: ShipProfile,
    env: EnvironmentalData,
    metrics: DerivedSegmentMetrics,
    config: Optional[ScoringConfig] = None,
) -> SegmentScores:
    """
    Evaluates all 6 individual normalized scores for a segment.

    Returns:
        SegmentScores dataclass containing time, fuel, wind, wave, current, and safety scores.
    """
    cfg = config or ScoringConfig()

    t_score = calculate_time_score(
        travel_time_hours=metrics.travel_time_hours,
        distance_nm=metrics.distance_nm,
        cruising_speed=ship.cruising_speed,
        config=cfg,
    )
    f_score = calculate_fuel_score(metrics=metrics, ship=ship, config=cfg)
    w_score = calculate_wind_score(
        wind_speed=env.wind_speed,
        relative_wind_dir=metrics.relative_wind_dir,
        config=cfg,
    )
    wv_score = calculate_wave_score(
        wave_height=env.wave_height,
        wave_direction=env.wave_direction,
        ship_bearing=metrics.bearing,
        wave_period=env.wave_period,
        config=cfg,
    )
    c_score = calculate_current_score(
        along_track_current=metrics.along_track_current,
        config=cfg,
    )
    s_score = calculate_safety_score(ship=ship, env=env, config=cfg)

    return SegmentScores(
        time_score=t_score,
        fuel_score=f_score,
        wind_score=w_score,
        wave_score=wv_score,
        current_score=c_score,
        safety_score=s_score,
    )
