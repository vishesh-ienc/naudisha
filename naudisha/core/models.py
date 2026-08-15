"""
Data models for NauDisha ship routing system.
Defines contracts for vessels, environmental conditions, navigational segments, and scoring weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Union


@dataclass(frozen=True)
class ShipProfile:
    """
    Static and hydrodynamic characteristics of a vessel.

    Attributes:
        ship_type: Vessel classification (e.g., 'Container', 'Bulk Carrier', 'Tanker').
        length: Overall length of the ship in meters (LOA).
        beam: Width of the ship at the widest point in meters.
        draft: Maximum submerged depth of the vessel in meters.
        cruising_speed: Design service speed in knots.
        maximum_speed: Maximum operational speed in knots.
    """
    ship_type: str
    length: float
    beam: float
    draft: float
    cruising_speed: float
    maximum_speed: float

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError("length must be positive.")
        if self.beam <= 0:
            raise ValueError("beam must be positive.")
        if self.draft <= 0:
            raise ValueError("draft must be positive.")
        if self.cruising_speed <= 0:
            raise ValueError("cruising_speed must be positive.")
        if self.maximum_speed < self.cruising_speed:
            raise ValueError("maximum_speed cannot be less than cruising_speed.")


@dataclass(frozen=True)
class EnvironmentalData:
    """
    Dynamic meteorological and oceanographic conditions at a given point in space and time.

    Attributes:
        timestamp: Time of observation or forecast (ISO string or datetime object).
        wind_speed: Wind speed in knots.
        wind_direction: Direction from which wind originates in degrees [0, 360) (meteorological convention).
        wave_height: Significant wave height (Hs) in meters.
        wave_direction: Direction towards/from which waves propagate in degrees [0, 360).
        wave_period: Peak wave period (Tp) in seconds.
        current_speed: Ocean surface current velocity in knots.
        current_direction: Direction towards which current flows in degrees [0, 360) (oceanographic convention).
    """
    timestamp: Union[datetime, str]
    wind_speed: float
    wind_direction: float
    wave_height: float
    wave_direction: float
    wave_period: float
    current_speed: float
    current_direction: float

    def __post_init__(self) -> None:
        if self.wind_speed < 0:
            raise ValueError("wind_speed cannot be negative.")
        if not (0 <= self.wind_direction <= 360):
            raise ValueError("wind_direction must be within [0, 360] degrees.")
        if self.wave_height < 0:
            raise ValueError("wave_height cannot be negative.")
        if not (0 <= self.wave_direction <= 360):
            raise ValueError("wave_direction must be within [0, 360] degrees.")
        if self.wave_period < 0:
            raise ValueError("wave_period cannot be negative.")
        if self.current_speed < 0:
            raise ValueError("current_speed cannot be negative.")
        if not (0 <= self.current_direction <= 360):
            raise ValueError("current_direction must be within [0, 360] degrees.")


@dataclass(frozen=True)
class SegmentData:
    """
    A single direct navigational segment between two geographic coordinates.

    Attributes:
        start_lat: Latitude of origin point (-90.0 to 90.0).
        start_lon: Longitude of origin point (-180.0 to 180.0).
        end_lat: Latitude of destination point (-90.0 to 90.0).
        end_lon: Longitude of destination point (-180.0 to 180.0).
        is_navigable: Flag indicating if this segment is safe and free of land/shallows.
    """
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    is_navigable: bool = True

    def __post_init__(self) -> None:
        if not (-90.0 <= self.start_lat <= 90.0) or not (-90.0 <= self.end_lat <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0 degrees.")
        if not (-180.0 <= self.start_lon <= 180.0) or not (-180.0 <= self.end_lon <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0 degrees.")


@dataclass(frozen=True)
class CostWeights:
    """
    User-configurable or profile-based weights for each cost factor.
    All weights default to 1.0.

    Attributes:
        time: Weight for travel time score.
        fuel: Weight for estimated fuel consumption / engine load score.
        wind: Weight for aerodynamic resistance score.
        wave: Weight for sea-state and wave impact score.
        current: Weight for hydrodynamic ocean current score.
        safety: Weight for vessel safety / extreme weather proximity score.
    """
    time: float = 1.0
    fuel: float = 1.0
    wind: float = 1.0
    wave: float = 1.0
    current: float = 1.0
    safety: float = 1.0

    def __post_init__(self) -> None:
        for factor, weight in (
            ("time", self.time),
            ("fuel", self.fuel),
            ("wind", self.wind),
            ("wave", self.wave),
            ("current", self.current),
            ("safety", self.safety),
        ):
            if weight < 0:
                raise ValueError(f"Weight for '{factor}' cannot be negative.")


@dataclass(frozen=True)
class ScoringConfig:
    """
    Configurable reference bounds used for min-max score normalization [0, 1].
    Allows replacing or tuning reference limits without hardcoding scientific assumptions.

    Attributes:
        min_travel_time_factor: Minimum travel time scaling factor relative to calm baseline (e.g. 0.8x).
        max_travel_time_factor: Maximum travel time scaling factor relative to calm baseline (e.g. 2.0x).
        max_reference_wind_speed: Maximum wind speed (knots) mapped to worst score 1.0.
        max_reference_wave_height: Maximum wave height (meters) mapped to worst score 1.0.
        max_reference_current_speed: Maximum current speed (knots) used for current score scaling.
        min_allowed_speed: Minimum effective speed (knots) to prevent stall/infinite time.
        safety_max_wave_height: Absolute safety wave height threshold (meters) for vessel.
        safety_max_wind_speed: Absolute safety wind speed threshold (knots) for vessel.
    """
    min_travel_time_factor: float = 0.7
    max_travel_time_factor: float = 2.0
    max_reference_wind_speed: float = 50.0  # knots
    max_reference_wave_height: float = 8.0   # meters
    max_reference_current_speed: float = 5.0 # knots
    min_allowed_speed: float = 0.5          # knots
    safety_max_wave_height: float = 10.0    # meters
    safety_max_wind_speed: float = 60.0     # knots


@dataclass(frozen=True)
class DerivedSegmentMetrics:
    """
    Hydrodynamic and geographic metrics calculated for a segment under specific environmental conditions.
    """
    distance_nm: float
    distance_km: float
    bearing: float
    relative_wind_dir: float
    relative_current_dir: float
    along_track_current: float
    effective_speed: float
    travel_time_hours: float


@dataclass(frozen=True)
class SegmentScores:
    """
    Individual normalized cost components clamped to [0.0, 1.0], where 0.0 = best and 1.0 = worst.
    """
    time_score: float
    fuel_score: float
    wind_score: float
    wave_score: float
    current_score: float
    safety_score: float


@dataclass(frozen=True)
class SegmentEvaluation:
    """
    Comprehensive evaluation of a navigational segment including metrics, scores, and final cost.
    """
    segment: SegmentData
    metrics: DerivedSegmentMetrics
    scores: SegmentScores
    weights: CostWeights
    total_cost: float
    is_navigable: bool
