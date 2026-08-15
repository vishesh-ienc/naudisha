"""
Geographic, nautical, and hydrodynamic derived calculations for ship routing.
Provides mathematically rigorous implementations for distance, bearing, relative angles,
along-track current decomposition, effective vessel speed, and travel time.
"""

from __future__ import annotations

import math
from typing import Optional

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    SegmentData,
    ScoringConfig,
    DerivedSegmentMetrics,
)

# Mean Earth radius in kilometers (WGS84 spherical approximation)
EARTH_RADIUS_KM: float = 6371.0088
# Conversion: 1 Nautical Mile = exactly 1.852 kilometers
KM_PER_NAUTICAL_MILE: float = 1.852
EARTH_RADIUS_NM: float = EARTH_RADIUS_KM / KM_PER_NAUTICAL_MILE


def calculate_haversine_distance(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    unit: str = "nm",
) -> float:
    """
    Calculates the great-circle distance between two points on a spherical Earth using the Haversine formula.

    Args:
        start_lat: Latitude of origin in degrees [-90, 90].
        start_lon: Longitude of origin in degrees [-180, 180].
        end_lat: Latitude of destination in degrees [-90, 90].
        end_lon: Longitude of destination in degrees [-180, 180].
        unit: 'nm' for nautical miles (default) or 'km' for kilometers.

    Returns:
        Great-circle distance in the specified unit.
    """
    lat1, lon1 = math.radians(start_lat), math.radians(start_lon)
    lat2, lon2 = math.radians(end_lat), math.radians(end_lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (math.sin(dlat / 2.0) ** 2) + math.cos(lat1) * math.cos(lat2) * (math.sin(dlon / 2.0) ** 2)
    # Clamp 'a' to [0.0, 1.0] to prevent domain errors due to floating-point precision
    a_clamped = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a_clamped), math.sqrt(1.0 - a_clamped))

    radius = EARTH_RADIUS_NM if unit.lower() == "nm" else EARTH_RADIUS_KM
    return radius * c


def calculate_bearing(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> float:
    """
    Calculates the initial great-circle forward azimuth (bearing) from origin to destination.

    Args:
        start_lat: Latitude of origin in degrees [-90, 90].
        start_lon: Longitude of origin in degrees [-180, 180].
        end_lat: Latitude of destination in degrees [-90, 90].
        end_lon: Longitude of destination in degrees [-180, 180].

    Returns:
        Initial bearing in degrees [0.0, 360.0).
    """
    lat1, lon1 = math.radians(start_lat), math.radians(start_lon)
    lat2, lon2 = math.radians(end_lat), math.radians(end_lon)

    dlon = lon2 - lon1

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    initial_bearing = math.atan2(y, x)
    initial_bearing_deg = (math.degrees(initial_bearing) + 360.0) % 360.0
    return initial_bearing_deg


def calculate_relative_direction(
    heading_deg: float,
    target_deg: float,
) -> float:
    """
    Computes the minimal angular deviation (relative angle) between two compass headings.

    Args:
        heading_deg: Reference heading/bearing in degrees [0, 360).
        target_deg: Target direction (wind/wave/current) in degrees [0, 360).

    Returns:
        Relative angle in degrees in the range [0.0, 180.0].
        (0° = directly aligned, 180° = directly opposing).
    """
    diff = abs(heading_deg - target_deg) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def calculate_along_track_current(
    current_speed: float,
    current_direction: float,
    ship_bearing: float,
) -> float:
    """
    Calculates the along-track ocean current velocity component relative to the ship's heading.

    Convention:
        - current_direction: Oceanographic direction towards which the current flows.
        - ship_bearing: Direction the ship is navigating towards.

    Returns:
        Along-track speed in knots.
        Positive (+) indicates a favorable / following current (assisting motion).
        Negative (-) indicates an opposing / head current (resisting motion).
    """
    angle_rad = math.radians(ship_bearing - current_direction)
    along_track = current_speed * math.cos(angle_rad)
    return along_track


def calculate_effective_speed(
    cruising_speed: float,
    along_track_current: float,
    maximum_speed: float,
    min_allowed_speed: float = 0.5,
) -> float:
    """
    Calculates the effective speed over ground (SOG) accounting for current drift and vessel limits.

    Args:
        cruising_speed: Vessel design cruising speed (knots).
        along_track_current: Current velocity along the track (knots).
        maximum_speed: Vessel maximum physical speed limit (knots).
        min_allowed_speed: Lower safety threshold to avoid zero or negative speed over ground.

    Returns:
        Effective speed over ground in knots, clamped within [min_allowed_speed, maximum_speed].
    """
    raw_effective = cruising_speed + along_track_current
    clamped_speed = max(min_allowed_speed, min(maximum_speed, raw_effective))
    return clamped_speed


def calculate_travel_time(
    distance_nm: float,
    effective_speed_knots: float,
) -> float:
    """
    Calculates the travel time required to navigate a segment.

    Args:
        distance_nm: Segment distance in nautical miles.
        effective_speed_knots: Speed over ground in knots (> 0).

    Returns:
        Travel time in hours.
    """
    if effective_speed_knots <= 0:
        raise ValueError("Effective speed must be strictly positive to calculate travel time.")
    return distance_nm / effective_speed_knots


def calculate_derived_metrics(
    segment: SegmentData,
    ship: ShipProfile,
    env: EnvironmentalData,
    config: Optional[ScoringConfig] = None,
) -> DerivedSegmentMetrics:
    """
    Orchestrates all derived calculations for a given segment, ship profile, and environmental state.

    Args:
        segment: Navigational segment.
        ship: Vessel characteristics.
        env: Dynamic environmental conditions.
        config: Optional scoring and limits configuration.

    Returns:
        DerivedSegmentMetrics containing distance, bearing, relative angles, speed, and time.
    """
    cfg = config or ScoringConfig()

    dist_nm = calculate_haversine_distance(
        segment.start_lat, segment.start_lon, segment.end_lat, segment.end_lon, unit="nm"
    )
    dist_km = dist_nm * KM_PER_NAUTICAL_MILE

    bearing = calculate_bearing(
        segment.start_lat, segment.start_lon, segment.end_lat, segment.end_lon
    )

    # Relative wind: angle between ship bearing and the direction wind comes from
    # (0° = headwind, 180° = tailwind)
    rel_wind = calculate_relative_direction(bearing, env.wind_direction)

    # Relative current: angle between ship bearing and the direction current flows towards
    # (0° = following current, 180° = opposing head current)
    rel_current = calculate_relative_direction(bearing, env.current_direction)

    along_current = calculate_along_track_current(
        current_speed=env.current_speed,
        current_direction=env.current_direction,
        ship_bearing=bearing,
    )

    eff_speed = calculate_effective_speed(
        cruising_speed=ship.cruising_speed,
        along_track_current=along_current,
        maximum_speed=ship.maximum_speed,
        min_allowed_speed=cfg.min_allowed_speed,
    )

    travel_time = calculate_travel_time(
        distance_nm=dist_nm,
        effective_speed_knots=eff_speed,
    )

    return DerivedSegmentMetrics(
        distance_nm=dist_nm,
        distance_km=dist_km,
        bearing=bearing,
        relative_wind_dir=rel_wind,
        relative_current_dir=rel_current,
        along_track_current=along_current,
        effective_speed=eff_speed,
        travel_time_hours=travel_time,
    )
