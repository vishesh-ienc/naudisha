"""
Marine and meteorological data integration provider (Interface / Future Roadmap).
Defines abstract contracts for acquiring ocean currents, wind vectors, and wave spectra
from open marine data providers (e.g., Copernicus Marine, NOAA GFS/WW3, ECMWF).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Union

from naudisha.core.models import EnvironmentalData


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
