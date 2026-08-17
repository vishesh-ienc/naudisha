"""
Copernicus Marine Service (CMEMS) real oceanographic data provider for NauDisha.
Fetches high-resolution physical ocean currents and spectral wave forecasts using the
official copernicusmarine toolbox and maps them into NauDisha's EnvironmentalData model.
"""

from __future__ import annotations

import math
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import WeatherProvider, BatchCapableProvider, ConditionRequest
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


class CopernicusMarineProvider(WeatherProvider, BatchCapableProvider):
    """
    Oceanographic data provider fetching real hydrodynamic currents and wave spectra
    from Copernicus Marine Service (CMEMS).

    Inherits both WeatherProvider (for single-point fetch_conditions) and
    BatchCapableProvider (for efficient multi-point fetch_conditions_batch).

    Batch strategy:
        Many requested points → bounding-box subset query (1 currents + 1 waves request)
        → local nearest-point extraction → N EnvironmentalData results.

    Data Flow:
        CMEMS Physics API (uo, vo) ──┐
                                     ├──► EnvironmentalData (Currents & Waves, Wind=None)
        CMEMS Waves API (Hs, dir, Tp)┘

    Attributes:
        currents_dataset_id: CMEMS dataset identifier for ocean physics/currents.
        waves_dataset_id: CMEMS dataset identifier for spectral waves.
        enable_cache: Enables in-memory caching of fetched observations.
        spatial_delta_deg: Bounding box padding for point and batch requests (default 0.1°).
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
        self._bbox_df_cache: Dict[str, Tuple[float, float, float, float, Any, Any]] = {}

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
            query_kwargs["minimum_depth"] = depth_level
            query_kwargs["maximum_depth"] = depth_level

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

    # -----------------------------------------------------------------------
    # Batch fetch (BatchCapableProvider implementation)
    # -----------------------------------------------------------------------

    def _execute_bbox_subset_query(
        self,
        dataset_id: str,
        variables: List[str],
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        start_dt: datetime,
        end_dt: datetime,
        depth_level: Optional[float] = None,
    ) -> Any:
        """
        Executes a bounding-box subset query covering multiple geographic points.

        Unlike _execute_subset_query (which adds spatial_delta around a single point),
        this method takes explicit bbox bounds already computed by the caller.
        The same credential checks, error mapping, and disable_progress_bar settings
        are applied as in the per-point method.

        Args:
            dataset_id: CMEMS dataset identifier.
            variables: List of variable names to fetch.
            lat_min, lat_max: Latitude bounds (degrees).
            lon_min, lon_max: Longitude bounds (degrees).
            start_dt, end_dt: UTC datetime range.
            depth_level: Optional depth (m) to constrain the query.

        Returns:
            DataFrame with all rows within the bounding box and time range.
        """
        import os
        from pathlib import Path

        has_env_creds = bool(
            os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME")
            and os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD")
        )
        cred_dir = Path.home() / ".copernicusmarine"
        has_file_creds = cred_dir.exists() and any(cred_dir.iterdir())

        if self._reader_fn is None and not (has_env_creds or has_file_creds):
            raise CopernicusAuthenticationError(
                "No local Copernicus Marine credentials found. "
                "Please run 'copernicusmarine login' to authenticate."
            )

        reader = self._get_reader()

        query_kwargs: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "variables": variables,
            "minimum_latitude": lat_min,
            "maximum_latitude": lat_max,
            "minimum_longitude": lon_min,
            "maximum_longitude": lon_max,
            "start_datetime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_datetime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "disable_progress_bar": True,
        }

        if depth_level is not None:
            query_kwargs["minimum_depth"] = depth_level
            query_kwargs["maximum_depth"] = depth_level

        try:
            df = reader(**query_kwargs)
            return df
        except Exception as exc:
            exc_str = str(exc).lower()
            if "credentials" in exc_str or "unauthorized" in exc_str or "login" in exc_str or "forbidden" in exc_str:
                raise CopernicusAuthenticationError(
                    f"Copernicus Marine authentication failed during batch query of '{dataset_id}'. Details: {exc}"
                ) from exc
            if "out of dataset bounds" in exc_str or "not found" in exc_str:
                raise CopernicusDataUnavailableError(
                    f"Batch bounding box [{lat_min:.3f}N-{lat_max:.3f}N, {lon_min:.3f}E-{lon_max:.3f}E] "
                    f"is out of bounds for dataset '{dataset_id}'. Details: {exc}"
                ) from exc
            raise CopernicusProviderError(
                f"Failed to batch-query Copernicus Marine dataset '{dataset_id}': {exc}"
            ) from exc

    def _extract_nearest_from_batch_df(
        self,
        df: Any,
        var_name: str,
        dataset_id: str,
        target_lat: float,
        target_lon: float,
    ) -> float:
        """
        Extracts the value of var_name from the closest row to (target_lat, target_lon)
        in a multi-row batch DataFrame.

        Nearest-point selection uses squared Euclidean distance in degree space:
            d^2 = (df.latitude - target_lat)^2 + (df.longitude - target_lon)^2

        This is valid for the small geographic extents used in NauDisha grids
        (typically < 5° x 5°) where degree-space distance is a sufficient proxy for
        geographic proximity and avoids expensive spherical distance computation.

        Args:
            df: DataFrame returned from _execute_bbox_subset_query.
            var_name: CMEMS variable column to extract.
            dataset_id: Dataset identifier (for error messages).
            target_lat, target_lon: Target geographic coordinates.

        Returns:
            float: Extracted scalar value.

        Raises:
            CopernicusDataUnavailableError: If df is empty, column missing, or nearest is NaN.
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            raise CopernicusDataUnavailableError(
                f"Empty batch response from '{dataset_id}' — no data in bounding box."
            )

        if var_name not in df.columns:
            raise CopernicusDataUnavailableError(
                f"Variable '{var_name}' not found in batch response columns: {list(df.columns)} "
                f"for dataset '{dataset_id}'."
            )

        # Identify latitude/longitude columns — copernicusmarine uses 'latitude'/'longitude'
        lat_col = next((c for c in df.columns if c.lower() in ("latitude", "lat")), None)
        lon_col = next((c for c in df.columns if c.lower() in ("longitude", "lon")), None)

        if lat_col is None or lon_col is None:
            # Fallback: use the first valid non-NaN row if spatial columns are unavailable
            valid_series = df[var_name].dropna()
            if valid_series.empty:
                raise CopernicusDataUnavailableError(
                    f"Variable '{var_name}' contains only NaN values in batch response for '{dataset_id}'."
                )
            val = float(valid_series.iloc[0])
        else:
            # Drop rows where variable is NaN
            valid_df = df.dropna(subset=[var_name])
            if valid_df.empty:
                raise CopernicusDataUnavailableError(
                    f"Variable '{var_name}' contains only NaN values in batch response for "
                    f"dataset '{dataset_id}' near ({target_lat:.4f}N, {target_lon:.4f}E)."
                )
            # Find nearest row by squared Euclidean distance in degree space
            dist_sq = (valid_df[lat_col] - target_lat) ** 2 + (valid_df[lon_col] - target_lon) ** 2
            nearest_idx = dist_sq.idxmin()
            val = float(valid_df.loc[nearest_idx, var_name])

        if math.isnan(val):
            raise CopernicusDataUnavailableError(
                f"NaN value for '{var_name}' nearest to ({target_lat:.4f}N, {target_lon:.4f}E) "
                f"in dataset '{dataset_id}'."
            )

        return val

    def _extract_nearest_multi_from_batch_df(
        self,
        df: Any,
        var_names: List[str],
        dataset_id: str,
        target_coords: List[Tuple[float, float]],
    ) -> Dict[str, List[float]]:
        """
        Extracts multiple variables for a list of target coordinates from a batch DataFrame.
        Uses scipy.spatial.cKDTree when available for sub-millisecond vectorized nearest-point lookup.
        Falls back to per-point _extract_nearest_from_batch_df if cKDTree is unavailable or data is irregular.
        """
        if df is None or (hasattr(df, "empty") and df.empty):
            raise CopernicusDataUnavailableError(
                f"Empty batch response from '{dataset_id}' — no data in bounding box."
            )

        for var in var_names:
            if var not in df.columns:
                raise CopernicusDataUnavailableError(
                    f"Variable '{var}' not found in batch response columns: {list(df.columns)} for '{dataset_id}'."
                )

        lat_col = next((c for c in df.columns if c.lower() in ("latitude", "lat")), None)
        lon_col = next((c for c in df.columns if c.lower() in ("longitude", "lon")), None)

        if lat_col is not None and lon_col is not None and len(target_coords) > 0:
            try:
                import numpy as np
                from scipy.spatial import cKDTree

                # Filter rows where variables and coordinates are not NaN
                valid_mask = df[var_names].notna().all(axis=1) & df[lat_col].notna() & df[lon_col].notna()
                valid_df = df[valid_mask]

                if not valid_df.empty:
                    pts = np.column_stack((valid_df[lat_col].to_numpy(dtype=float), valid_df[lon_col].to_numpy(dtype=float)))
                    tree = cKDTree(pts)

                    query_pts = np.array(target_coords, dtype=float)
                    _, nearest_indices = tree.query(query_pts)

                    out: Dict[str, List[float]] = {}
                    for var in var_names:
                        arr = valid_df[var].to_numpy(dtype=float)
                        out[var] = [float(v) for v in arr[nearest_indices]]
                    return out
            except Exception as exc:
                logger.debug("Vectorized KDTree extraction failed, falling back to per-point extraction: %s", exc)

        # Fallback to per-point extraction
        out_fallback: Dict[str, List[float]] = {v: [] for v in var_names}
        for lat, lon in target_coords:
            for var in var_names:
                val = self._extract_nearest_from_batch_df(df, var, dataset_id, lat, lon)
                out_fallback[var].append(val)
        return out_fallback

    def fetch_conditions_batch(
        self,
        requests: List["ConditionRequest"],
    ) -> Dict["ConditionRequest", EnvironmentalData]:
        """
        Fetches environmental conditions for multiple geographic points using spatial
        bounding-box queries, dramatically reducing the number of remote CMEMS API calls.

        Batch strategy:
            N requested points (same timestamp) → bounding box →
            1 currents subset request + 1 waves subset request (concurrent) →
            cKDTree vectorized nearest-point extraction for all points in <1ms →
            N EnvironmentalData results.

        For different timestamps, requests are grouped by temporal hour-bucket so that
        points sharing the same hour-bucket are served by a single pair of requests.

        Network request count:
            Old: N points × 2 datasets = 2N requests
            New: T timestamp-buckets × 2 datasets = 2T requests  (T << N for grids)

        Args:
            requests: Sequence of ConditionRequest objects.

        Returns:
            Dict mapping each ConditionRequest to its EnvironmentalData.

        Raises:
            ValueError: If any request has invalid lat/lon.
            CopernicusAuthenticationError: If CMEMS authentication fails.
            CopernicusDataUnavailableError: If a point or variable has no data.
            CopernicusProviderError: For other CMEMS failures.
        """
        if not requests:
            return {}

        # Validate all coordinates upfront
        for req in requests:
            if not (-90.0 <= req.lat <= 90.0):
                raise ValueError(f"Latitude {req.lat} is out of valid range [-90.0, 90.0].")
            if not (-180.0 <= req.lon <= 180.0):
                raise ValueError(f"Longitude {req.lon} is out of valid range [-180.0, 180.0].")

        results: Dict["ConditionRequest", EnvironmentalData] = {}

        # --- Check cache for all requests first ---
        uncached: List["ConditionRequest"] = []
        for req in requests:
            dt_utc = _normalize_utc_datetime(req.timestamp)
            cache_key = (round(req.lat, 2), round(req.lon, 2), dt_utc.strftime("%Y-%m-%dT%H"))
            if self.enable_cache and cache_key in self._cache:
                results[req] = self._cache[cache_key]
            else:
                uncached.append(req)

        if not uncached:
            return results

        # --- Group uncached requests by temporal hour-bucket ---
        from collections import defaultdict
        bucket_map: Dict[str, List["ConditionRequest"]] = defaultdict(list)
        for req in uncached:
            dt_utc = _normalize_utc_datetime(req.timestamp)
            bucket_key = dt_utc.strftime("%Y-%m-%dT%H")
            bucket_map[bucket_key].append(req)

        # --- Process each temporal bucket with ONE currents + ONE waves request ---
        for bucket_key, bucket_requests in bucket_map.items():
            lats = [req.lat for req in bucket_requests]
            lons = [req.lon for req in bucket_requests]

            # Compute bounding box with safety margin for nearest selection
            lat_min = min(lats) - self.spatial_delta_deg
            lat_max = max(lats) + self.spatial_delta_deg
            lon_min = min(lons) - self.spatial_delta_deg
            lon_max = max(lons) + self.spatial_delta_deg

            # Use the bucket representative time ± temporal_delta_hours
            bucket_dt = _normalize_utc_datetime(bucket_requests[0].timestamp)
            start_dt = bucket_dt - timedelta(hours=self.temporal_delta_hours)
            end_dt = bucket_dt + timedelta(hours=self.temporal_delta_hours)

            # Check if points fall within an existing cached bounding box DataFrame
            cached_bbox = self._bbox_df_cache.get(bucket_key) if self.enable_cache else None
            if (
                cached_bbox is not None
                and lat_min >= cached_bbox[0]
                and lat_max <= cached_bbox[1]
                and lon_min >= cached_bbox[2]
                and lon_max <= cached_bbox[3]
            ):
                df_cur = cached_bbox[4]
                df_wav = cached_bbox[5]
            else:
                # ONE currents + ONE waves request for the entire bucket, issued concurrently.
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix="cmems") as pool:
                    fut_cur = pool.submit(
                        self._execute_bbox_subset_query,
                        dataset_id=self.currents_dataset_id,
                        variables=["uo", "vo"],
                        lat_min=lat_min,
                        lat_max=lat_max,
                        lon_min=lon_min,
                        lon_max=lon_max,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        depth_level=CMEMS_OCEAN_CURRENTS_SPEC.depth_level,
                    )
                    fut_wav = pool.submit(
                        self._execute_bbox_subset_query,
                        dataset_id=self.waves_dataset_id,
                        variables=["VHM0", "VMDR", "VTPK"],
                        lat_min=lat_min,
                        lat_max=lat_max,
                        lon_min=lon_min,
                        lon_max=lon_max,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        depth_level=None,
                    )
                    df_cur = fut_cur.result()
                    df_wav = fut_wav.result()

                if self.enable_cache:
                    self._bbox_df_cache[bucket_key] = (lat_min, lat_max, lon_min, lon_max, df_cur, df_wav)

            # Vectorized nearest-point extraction using cKDTree
            target_coords = [(req.lat, req.lon) for req in bucket_requests]
            cur_extracted = self._extract_nearest_multi_from_batch_df(
                df_cur, ["uo", "vo"], self.currents_dataset_id, target_coords
            )
            wav_extracted = self._extract_nearest_multi_from_batch_df(
                df_wav, ["VHM0", "VMDR", "VTPK"], self.waves_dataset_id, target_coords
            )

            for i, req in enumerate(bucket_requests):
                dt_utc = _normalize_utc_datetime(req.timestamp)
                cache_key = (round(req.lat, 2), round(req.lon, 2), dt_utc.strftime("%Y-%m-%dT%H"))

                uo_val = cur_extracted["uo"][i]
                vo_val = cur_extracted["vo"][i]
                current_speed, current_direction = convert_current_vectors_to_speed_and_direction(
                    uo_mps=uo_val, vo_mps=vo_val
                )

                vhm0_val = wav_extracted["VHM0"][i]
                vmdr_val = wav_extracted["VMDR"][i]
                vtpk_val = wav_extracted["VTPK"][i]

                env = EnvironmentalData(
                    timestamp=dt_utc.isoformat(),
                    wind_speed=None,
                    wind_direction=None,
                    wave_height=vhm0_val,
                    wave_direction=vmdr_val,
                    wave_period=vtpk_val,
                    current_speed=current_speed,
                    current_direction=current_direction,
                )

                results[req] = env
                if self.enable_cache:
                    self._cache[cache_key] = env

        return results
