"""
Composite marine and atmospheric environmental data provider for NauDisha.
Combines Copernicus Marine Service (ocean currents and spectral waves) with Open-Meteo
(atmospheric wind vectors) into a unified, complete EnvironmentalData observation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import WeatherProvider
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.data.wind_provider import OpenMeteoWindProvider


class CompositeEnvironmentalProvider(WeatherProvider):
    """
    Unified environmental data provider combining Copernicus Marine (ocean currents & waves)
    and Open-Meteo (atmospheric wind vectors).

    Data Fusion:
        Copernicus Marine (uo, vo, Hs, dir, Tp) ──┐
                                                  ├──► Unified EnvironmentalData
        Open-Meteo (wind speed, wind direction) ──┘
    """

    def __init__(
        self,
        marine_provider: Optional[CopernicusMarineProvider] = None,
        wind_provider: Optional[OpenMeteoWindProvider] = None,
    ) -> None:
        """
        Initializes the composite environmental provider.

        Args:
            marine_provider: Copernicus Marine provider instance (defaults to new instance).
            wind_provider: Open-Meteo wind provider instance (defaults to new instance).
        """
        self.marine_provider = marine_provider or CopernicusMarineProvider()
        self.wind_provider = wind_provider or OpenMeteoWindProvider()

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        """
        Fetches combined marine and atmospheric conditions at the specified coordinates and time.

        Args:
            lat: Latitude in degrees [-90.0, 90.0].
            lon: Longitude in degrees [-180.0, 180.0].
            timestamp: Observation/forecast timestamp.

        Returns:
            Fully populated EnvironmentalData object containing all 7 physical parameters.
        """
        # 1. Fetch ocean currents and spectral waves from Copernicus Marine
        marine_data = self.marine_provider.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)

        # 2. Fetch atmospheric wind from Open-Meteo
        wind_speed, wind_direction = self.wind_provider.fetch_wind(lat=lat, lon=lon, timestamp=timestamp)

        # 3. Fuse into unified EnvironmentalData model
        return EnvironmentalData(
            timestamp=marine_data.timestamp,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            wave_height=marine_data.wave_height,
            wave_direction=marine_data.wave_direction,
            wave_period=marine_data.wave_period,
            current_speed=marine_data.current_speed,
            current_direction=marine_data.current_direction,
        )
