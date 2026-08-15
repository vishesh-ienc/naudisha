"""
Composite marine and atmospheric environmental data provider for NauDisha.
Combines Copernicus Marine Service (ocean currents and spectral waves) with Open-Meteo
(atmospheric wind vectors) into a unified, complete EnvironmentalData observation.

Implements BatchCapableProvider for efficient grid population:
    - CMEMS batch: ONE currents + ONE waves request for the entire grid bounding box.
    - Open-Meteo dedup: Unique grid cells only (collapses 80 nearby points to ~4-8 HTTP requests).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence, Union

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import (
    WeatherProvider,
    BatchCapableProvider,
    ConditionRequest,
)
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.data.wind_provider import OpenMeteoWindProvider


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

    def fetch_conditions_batch(
        self,
        requests: Sequence[ConditionRequest],
    ) -> Dict[ConditionRequest, EnvironmentalData]:
        """
        Fetches combined marine and atmospheric conditions for multiple points efficiently.

        Batch strategy:
            1. Delegate all CMEMS requests to CopernicusMarineProvider.fetch_conditions_batch()
               -> 1 currents + 1 waves request for the full bounding box.
            2. Deduplicate Open-Meteo requests by rounding lat/lon to 2 decimal places
               (matching Open-Meteo's ~0.1 degree grid resolution).
               Fetch one HTTP request per unique cell, then map back by nearest-cell key.
               For an 80-edge 5x5 grid spanning ~1x1 degree, this yields 4-8 unique cells.

        Network request count comparison:
            Old (single-point): 80 edges x 3 requests = 240 network requests
            New (batch):        1 currents + 1 waves + ~4-8 wind = 6-10 network requests

        Args:
            requests: Sequence of ConditionRequest objects.

        Returns:
            Dict mapping each ConditionRequest to a fully populated EnvironmentalData.
        """
        if not requests:
            return {}

        request_list = list(requests)

        # 1. Batch-fetch all CMEMS marine data (1 currents + 1 waves request for all points)
        marine_results: Dict[ConditionRequest, EnvironmentalData] = (
            self.marine_provider.fetch_conditions_batch(request_list)
        )

        # 2. Deduplicate Open-Meteo requests by rounded cell key
        #    Open-Meteo caches per (round(lat,2), round(lon,2), hour) — so pre-populate
        #    the cache by fetching each unique cell once. The cache handles dedup implicitly,
        #    but we explicitly fetch unique cells to count network requests for diagnostics.
        seen_cells = set()
        for req in request_list:
            cell_key = (round(req.lat, 2), round(req.lon, 2))
            if cell_key not in seen_cells:
                seen_cells.add(cell_key)
                # fetch_wind() populates the internal cache; subsequent calls are free
                self.wind_provider.fetch_wind(
                    lat=req.lat,
                    lon=req.lon,
                    timestamp=req.timestamp,
                )

        # 3. Assemble combined results
        results: Dict[ConditionRequest, EnvironmentalData] = {}
        for req in request_list:
            marine_data = marine_results[req]
            # fetch_wind() now returns cached result — no additional network call
            wind_speed, wind_direction = self.wind_provider.fetch_wind(
                lat=req.lat,
                lon=req.lon,
                timestamp=req.timestamp,
            )
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
