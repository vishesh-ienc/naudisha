"""
Copernicus Marine Service (CMEMS) real oceanographic data provider for NauDisha.
Fetches high-resolution physical ocean currents and spectral wave forecasts using the
official copernicusmarine toolbox and maps them into NauDisha's EnvironmentalData model.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import WeatherProvider
from naudisha.data.copernicus_schema import (
    CMEMS_OCEAN_CURRENTS_SPEC,
    CMEMS_WAVES_SPEC,
    convert_current_vectors_to_speed_and_direction,
)

logger = logging.getLogger(__name__)


class CopernicusProviderError(Exception):
    """Base exception for all Copernicus Marine provider failures."""
    pass


class CopernicusAuthenticationError(CopernicusProviderError):
    """Raised when Copernicus Marine authentication fails or credentials are missing."""
    pass


class CopernicusDataUnavailableError(CopernicusProviderError):
    """Raised when requested geographic coordinates, depth, or timestamp return no data."""
    pass


def _normalize_utc_datetime(timestamp: Union[datetime, str]) -> datetime:
    """Parses and normalizes a timestamp string or datetime object into a timezone-aware UTC datetime."""
    if isinstance(timestamp, str):
        # Handle ISO strings like 2026-08-16T12:00:00Z or 2026-08-16 12:00:00
        cleaned = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    elif isinstance(timestamp, datetime):
        dt = timestamp
    else:
        raise CopernicusProviderError(f"Invalid timestamp type: {type(timestamp)}. Expected datetime or ISO string.")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


class CopernicusMarineProvider(WeatherProvider):
    """
    Oceanographic data provider fetching real hydrodynamic currents and wave spectra
    from Copernicus Marine Service (CMEMS).

    Data Flow:
        CMEMS Physics API (uo, vo) ──┐
                                     ├──► EnvironmentalData (Currents & Waves, Wind=None)
        CMEMS Waves API (Hs, dir, Tp)┘

    Attributes:
        currents_dataset_id: CMEMS dataset identifier for ocean physics/currents.
        waves_dataset_id: CMEMS dataset identifier for spectral waves.
        enable_cache: Enables in-memory caching of fetched observations.
        spatial_delta_deg: Bounding box padding for targeted point requests (default 0.1°).
        temporal_delta_hours: Time window search radius (default 3 hours).
    """

    def __init__(
        self,
        currents_dataset_id: str = CMEMS_OCEAN_CURRENTS_SPEC.dataset_id,
        waves_dataset_id: str = CMEMS_WAVES_SPEC.dataset_id,
        enable_cache: bool = True,
        spatial_delta_deg: float = 0.1,
        temporal_delta_hours: float = 3.0,
        reader_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Initializes the Copernicus Marine data provider.

        Args:
            currents_dataset_id: Copernicus dataset ID for ocean currents.
            waves_dataset_id: Copernicus dataset ID for wave parameters.
            enable_cache: When True, caches spatial/temporal queries in memory.
            spatial_delta_deg: Half-width of spatial bounding box subset query.
            temporal_delta_hours: Half-width of temporal slice query.
            reader_fn: Optional callable for fetching DataFrame (used for dependency injection / offline testing).
        """
        self.currents_dataset_id = currents_dataset_id
        self.waves_dataset_id = waves_dataset_id
        self.enable_cache = enable_cache
        self.spatial_delta_deg = spatial_delta_deg
        self.temporal_delta_hours = temporal_delta_hours
        self._reader_fn = reader_fn
        self._cache: Dict[Tuple[float, float, str], EnvironmentalData] = {}

    def _get_reader(self) -> Callable[..., Any]:
        """Returns the active dataframe reader function (injected reader or copernicusmarine.read_dataframe)."""
        if self._reader_fn is not None:
            return self._reader_fn

        try:
            import copernicusmarine
            return copernicusmarine.read_dataframe
        except ImportError as err:
            raise CopernicusProviderError(
                "The 'copernicusmarine' package is required to use CopernicusMarineProvider. "
                "Install it via 'pip install copernicusmarine' or 'pip install .[marine]'."
            ) from err

    def _execute_subset_query(
        self,
        dataset_id: str,
        variables: List[str],
        lat: float,
        lon: float,
        dt_utc: datetime,
        depth_level: Optional[float] = None,
    ) -> Any:
        """
        Executes a targeted, minimal spatial/temporal subset query via copernicusmarine.read_dataframe.
        """
        import os
        from pathlib import Path

        # Pre-flight check: ensure credentials exist in environment or ~/.copernicusmarine to avoid interactive stdin prompt
        has_env_creds = bool(os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME") and os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD"))
        cred_dir = Path.home() / ".copernicusmarine"
        has_file_creds = cred_dir.exists() and any(cred_dir.iterdir())

        if self._reader_fn is None and not (has_env_creds or has_file_creds):
            raise CopernicusAuthenticationError(
                "No local Copernicus Marine credentials found in ~/.copernicusmarine/ or environment variables. "
                "Please run 'copernicusmarine login' in your terminal to authenticate with your Copernicus account."
            )

        reader = self._get_reader()

        lat_min = lat - self.spatial_delta_deg
        lat_max = lat + self.spatial_delta_deg
        lon_min = lon - self.spatial_delta_deg
        lon_max = lon + self.spatial_delta_deg

        start_dt = dt_utc - timedelta(hours=self.temporal_delta_hours)
        end_dt = dt_utc + timedelta(hours=self.temporal_delta_hours)

        query_kwargs: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "variables": variables,
            "minimum_latitude": lat_min,
            "maximum_latitude": lat_max,
            "minimum_longitude": lon_min,
            "maximum_longitude": lon_max,
            "start_datetime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_datetime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "coordinates_selection_method": "nearest",
            "disable_progress_bar": True,
        }

        if depth_level is not None:
            query_kwargs["minimum_depth"] = max(0.0, depth_level - 0.5)
            query_kwargs["maximum_depth"] = depth_level + 0.5

        try:
            df = reader(**query_kwargs)
            return df
        except Exception as exc:
            exc_str = str(exc).lower()
            if "credentials" in exc_str or "unauthorized" in exc_str or "login" in exc_str or "forbidden" in exc_str:
                raise CopernicusAuthenticationError(
                    f"Copernicus Marine authentication failed while querying dataset '{dataset_id}'. "
                    f"Ensure you are logged in via 'copernicusmarine login'. Details: {exc}"
                ) from exc
            if "out of dataset bounds" in exc_str or "not found" in exc_str:
                raise CopernicusDataUnavailableError(
                    f"Requested coordinates ({lat:.4f}N, {lon:.4f}E) or time {dt_utc.isoformat()} "
                    f"are out of bounds for dataset '{dataset_id}'. Details: {exc}"
                ) from exc
            raise CopernicusProviderError(
                f"Failed to query Copernicus Marine dataset '{dataset_id}': {exc}"
            ) from exc

    def _extract_nearest_scalar(
        self,
        df: Any,
        var_name: str,
        dataset_id: str,
        lat: float,
        lon: float,
    ) -> float:
        """Extracts a valid float scalar from the returned DataFrame, verifying column existence and NaN status."""
        if df is None or (hasattr(df, "empty") and df.empty):
            raise CopernicusDataUnavailableError(
                f"No data returned from Copernicus Marine dataset '{dataset_id}' for point ({lat:.4f}N, {lon:.4f}E)."
            )

        if var_name not in df.columns:
            raise CopernicusDataUnavailableError(
                f"Variable '{var_name}' not found in Copernicus response columns: {list(df.columns)} for dataset '{dataset_id}'."
            )

        # Drop NaNs for the variable
        valid_series = df[var_name].dropna()
        if valid_series.empty:
            raise CopernicusDataUnavailableError(
                f"Variable '{var_name}' contains only NaN values for point ({lat:.4f}N, {lon:.4f}E) in dataset '{dataset_id}'."
            )

        val = float(valid_series.iloc[0])
        if math.isnan(val):
            raise CopernicusDataUnavailableError(
                f"Invalid NaN value for '{var_name}' at ({lat:.4f}N, {lon:.4f}E) in dataset '{dataset_id}'."
            )

        return val

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        """
        Fetches dynamic ocean currents and wave conditions from Copernicus Marine for specified coordinates and timestamp.

        Wind data is not provided by this service and is explicitly returned as None.

        Args:
            lat: Latitude in degrees [-90.0, 90.0].
            lon: Longitude in degrees [-180.0, 180.0].
            timestamp: Observation/forecast timestamp.

        Returns:
            Populated EnvironmentalData object with current and wave parameters.
        """
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude {lat} is out of valid range [-90.0, 90.0].")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude {lon} is out of valid range [-180.0, 180.0].")

        dt_utc = _normalize_utc_datetime(timestamp)
        cache_key = (round(lat, 2), round(lon, 2), dt_utc.strftime("%Y-%m-%dT%H"))

        if self.enable_cache and cache_key in self._cache:
            logger.debug("Returning cached Copernicus conditions for key %s", cache_key)
            return self._cache[cache_key]

        # 1. Fetch Ocean Currents (uo, vo)
        df_cur = self._execute_subset_query(
            dataset_id=self.currents_dataset_id,
            variables=["uo", "vo"],
            lat=lat,
            lon=lon,
            dt_utc=dt_utc,
            depth_level=CMEMS_OCEAN_CURRENTS_SPEC.depth_level,
        )
        uo_val = self._extract_nearest_scalar(df_cur, "uo", self.currents_dataset_id, lat, lon)
        vo_val = self._extract_nearest_scalar(df_cur, "vo", self.currents_dataset_id, lat, lon)

        calc_current_speed, calc_current_direction = convert_current_vectors_to_speed_and_direction(
            uo_mps=uo_val,
            vo_mps=vo_val,
        )

        # 2. Fetch Ocean Waves (VHM0, VMDR, VTPK)
        df_wav = self._execute_subset_query(
            dataset_id=self.waves_dataset_id,
            variables=["VHM0", "VMDR", "VTPK"],
            lat=lat,
            lon=lon,
            dt_utc=dt_utc,
            depth_level=None,
        )
        vhm0_val = self._extract_nearest_scalar(df_wav, "VHM0", self.waves_dataset_id, lat, lon)
        vmdr_val = self._extract_nearest_scalar(df_wav, "VMDR", self.waves_dataset_id, lat, lon)
        vtpk_val = self._extract_nearest_scalar(df_wav, "VTPK", self.waves_dataset_id, lat, lon)

        # 3. Construct EnvironmentalData (Wind fields are explicitly None)
        env = EnvironmentalData(
            timestamp=dt_utc.isoformat(),
            wind_speed=None,
            wind_direction=None,
            wave_height=vhm0_val,
            wave_direction=vmdr_val,
            wave_period=vtpk_val,
            current_speed=calc_current_speed,
            current_direction=calc_current_direction,
        )

        if self.enable_cache:
            self._cache[cache_key] = env

        return env
