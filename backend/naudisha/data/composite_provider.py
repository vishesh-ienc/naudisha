"""
Composite marine and atmospheric environmental data provider for NauDisha.
Combines Copernicus Marine Service (ocean currents and spectral waves) with Open-Meteo
(atmospheric wind vectors) into a unified, complete EnvironmentalData observation.

Implements BatchCapableProvider for efficient grid population:
    - CMEMS batch: ONE currents + ONE waves request for the entire grid bounding box.
    - Open-Meteo dedup: Unique grid cells only (collapses 80 nearby points to ~4-8 HTTP requests).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import (
    WeatherProvider,
    BatchCapableProvider,
    ConditionRequest,
)
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.data.wind_provider import (
    OpenMeteoWindProvider,
    _get_climatological_wind,
    _normalize_utc_datetime,
)


class CompositeEnvironmentalProvider(WeatherProvider, BatchCapableProvider):
    """
    Unified environmental data provider combining Copernicus Marine (ocean currents & waves)
    and Open-Meteo (atmospheric wind vectors).

    Implements both WeatherProvider (single-point) and BatchCapableProvider (multi-point)
    interfaces. The batch path drastically reduces network requests when populating a
    geographic grid:

        Single-point path (fetch_conditions):
            1 currents + 1 waves + 1 wind request per edge

        Batch path (fetch_conditions_batch):
            1 currents + 1 waves request for entire grid bbox
            + 1 wind request per unique Open-Meteo grid cell (typically 4-8 for a 5x5 grid)

    Data Fusion:
        Copernicus Marine (uo, vo, Hs, dir, Tp) --+
                                                   +--> Unified EnvironmentalData
        Open-Meteo (wind speed, wind direction)  --+
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
        Fetches combined marine and atmospheric conditions concurrently at the specified coordinates and time.

        Args:
            lat: Latitude in degrees [-90.0, 90.0].
            lon: Longitude in degrees [-180.0, 180.0].
            timestamp: Observation/forecast timestamp.

        Returns:
            Fully populated EnvironmentalData object containing all 7 physical parameters.
        """
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="env_single") as pool:
            fut_marine = pool.submit(self.marine_provider.fetch_conditions, lat=lat, lon=lon, timestamp=timestamp)
            fut_wind = pool.submit(self.wind_provider.fetch_wind, lat=lat, lon=lon, timestamp=timestamp)
            marine_data = fut_marine.result()
            try:
                wind_speed, wind_direction = fut_wind.result()
            except Exception as exc:
                logger.warning("Open-Meteo single wind fetch failed (%s), defaulting to seasonal monsoon wind model.", exc)
                dt_utc = _normalize_utc_datetime(timestamp)
                wind_speed, wind_direction = _get_climatological_wind(lat, lon, dt_utc)

        # Fuse into unified EnvironmentalData model
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

    def fetch_conditions_batch(
        self,
        requests: Sequence[ConditionRequest],
    ) -> Dict[ConditionRequest, EnvironmentalData]:
        """
        Fetches combined marine and atmospheric conditions for multiple points concurrently.

        Batch concurrency strategy:
            1. Concurrently launch Copernicus Marine batch query (currents + waves bbox)
               and Open-Meteo batch query (multi-location native array query).
            2. Both independent providers execute in parallel threads.
            3. Fuse oceanographic (CMEMS) and atmospheric (Open-Meteo) vectors into unified EnvironmentalData.

        Args:
            requests: Sequence of ConditionRequest objects.

        Returns:
            Dict mapping each ConditionRequest to a fully populated EnvironmentalData.
        """
        if not requests:
            return {}

        request_list = list(requests)

        # 1 & 2. Concurrently fetch CMEMS marine batch and Open-Meteo wind batch in parallel
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="env_batch") as pool:
            fut_marine = pool.submit(self.marine_provider.fetch_conditions_batch, request_list)
            fut_wind = pool.submit(self.wind_provider.fetch_wind_batch, request_list)
            try:
                marine_results = fut_marine.result(timeout=6.0)
            except Exception as exc:
                logger.warning("Copernicus Marine batch query timed out or failed (%s), defaulting to hydrodynamic baseline.", exc)
                marine_results = {
                    req: EnvironmentalData(
                        timestamp=req.timestamp if isinstance(req.timestamp, str) else req.timestamp.isoformat(),
                        wave_height=1.5,
                        wave_direction=220.0,
                        wave_period=7.0,
                        current_speed=0.8,
                        current_direction=90.0,
                    )
                    for req in request_list
                }
            try:
                wind_results = fut_wind.result(timeout=4.0)
            except Exception as exc:
                logger.warning("Open-Meteo batch wind fetch failed (%s), defaulting to seasonal monsoon wind model.", exc)
                wind_results = {
                    req: _get_climatological_wind(req.lat, req.lon, _normalize_utc_datetime(req.timestamp))
                    for req in request_list
                }

        # 3. Assemble combined results
        results: Dict[ConditionRequest, EnvironmentalData] = {}
        for req in request_list:
            marine_data = marine_results[req]
            wind_speed, wind_direction = wind_results.get(req, _get_climatological_wind(req.lat, req.lon, _normalize_utc_datetime(req.timestamp)))
            results[req] = EnvironmentalData(
                timestamp=marine_data.timestamp,
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                wave_height=marine_data.wave_height,
                wave_direction=marine_data.wave_direction,
                wave_period=marine_data.wave_period,
                current_speed=marine_data.current_speed,
                current_direction=marine_data.current_direction,
            )

        return results
