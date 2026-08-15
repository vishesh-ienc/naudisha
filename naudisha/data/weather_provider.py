"""
Marine and meteorological data integration provider (Interface / Future Roadmap).
Defines abstract contracts for acquiring ocean currents, wind vectors, and wave spectra
from open marine data providers (e.g., Copernicus Marine, NOAA GFS/WW3, ECMWF).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Sequence, Union

from naudisha.core.models import EnvironmentalData


@dataclass(frozen=True)
class ConditionRequest:
    """
    A single request for environmental conditions at a geographic point and time.

    Used as the element type for batch fetch operations.

    Attributes:
        lat: Latitude in degrees [-90.0, 90.0].
        lon: Longitude in degrees [-180.0, 180.0].
        timestamp: Observation/forecast timestamp (ISO string or datetime).
    """
    lat: float
    lon: float
    timestamp: Union[datetime, str]


class WeatherProvider(ABC):
    """Abstract interface for marine/weather data ingestion."""

    @abstractmethod
    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        """Fetches dynamic marine/weather parameters at specified coordinates and time."""
        pass


class BatchCapableProvider(ABC):
    """
    Optional mixin for providers that support efficient batch fetching of environmental data.

    Providers implementing this interface can serve many geographic points from a small
    number of remote requests by fetching over a bounding box and performing local
    nearest-point extraction on the returned dataset.

    This is a separate ABC from WeatherProvider so that existing providers are not broken.
    The graph layer detects batch capability via isinstance(provider, BatchCapableProvider).
    """

    @abstractmethod
    def fetch_conditions_batch(
        self,
        requests: Sequence[ConditionRequest],
    ) -> Dict[ConditionRequest, EnvironmentalData]:
        """
        Fetches environmental conditions for multiple geographic points efficiently.

        Implementations are expected to minimize the number of remote API calls by
        grouping requests into bounding-box queries, then performing local nearest-point
        lookup on the returned dataset.

        Args:
            requests: Sequence of ConditionRequest objects, each specifying lat, lon, timestamp.

        Returns:
            Mapping from each ConditionRequest to its corresponding EnvironmentalData.
            All input requests must have a corresponding entry in the returned mapping.
        """
        pass



class MockWeatherProvider(WeatherProvider):
    """Mock weather provider for local deterministic testing and simulation."""

    def __init__(
        self,
        default_wind_speed: float = 15.0,
        default_wind_dir: float = 90.0,
        default_wave_height: float = 1.5,
        default_wave_dir: float = 90.0,
        default_wave_period: float = 7.0,
        default_current_speed: float = 1.0,
        default_current_dir: float = 45.0,
    ) -> None:
        self.default_wind_speed = default_wind_speed
        self.default_wind_dir = default_wind_dir
        self.default_wave_height = default_wave_height
        self.default_wave_dir = default_wave_dir
        self.default_wave_period = default_wave_period
        self.default_current_speed = default_current_speed
        self.default_current_dir = default_current_dir

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        return EnvironmentalData(
            timestamp=timestamp,
            wind_speed=self.default_wind_speed,
            wind_direction=self.default_wind_dir,
            wave_height=self.default_wave_height,
            wave_direction=self.default_wave_dir,
            wave_period=self.default_wave_period,
            current_speed=self.default_current_speed,
            current_direction=self.default_current_dir,
        )
