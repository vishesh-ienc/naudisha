"""
Open-Meteo atmospheric wind data provider for NauDisha.
Fetches high-resolution 10-meter wind speed and direction forecasts from the free Open-Meteo
atmospheric forecast endpoint, converts units to nautical standards (knots, degrees), and
maps them into NauDisha's EnvironmentalData model.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from naudisha.core.models import EnvironmentalData
from naudisha.data.weather_provider import WeatherProvider

logger = logging.getLogger(__name__)

# Standard conversion constants
KMH_TO_KNOTS: float = 0.5399568035
MS_TO_KNOTS: float = 1.9438444924


class WindProviderError(Exception):
    """Base exception for all atmospheric wind provider failures."""
    pass


class WindNetworkError(WindProviderError):
    """Raised when an HTTP error, DNS failure, or connection timeout occurs."""
    pass


class WindDataUnavailableError(WindProviderError):
    """Raised when coordinates or timestamp return empty/NaN data or are out of bounds."""
    pass


class WindResponseMalformedError(WindProviderError):
    """Raised when the API response payload is missing required schema fields or contains invalid JSON."""
    pass


def _normalize_utc_datetime(timestamp: Union[datetime, str]) -> datetime:
    """Parses and normalizes a timestamp string or datetime object into a timezone-aware UTC datetime."""
    if isinstance(timestamp, str):
        cleaned = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    elif isinstance(timestamp, datetime):
        dt = timestamp
    else:
        raise WindProviderError(f"Invalid timestamp type: {type(timestamp)}. Expected datetime or ISO string.")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


# Global shared in-memory wind cache across service calls: (snapped_lat, snapped_lon, YYYY-MM-DDTHH) -> (speed_knots, direction_deg)
_GLOBAL_WIND_CACHE: Dict[Tuple[float, float, str], Tuple[float, float]] = {}


def _to_cache_key(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float, str]:
    """Snaps coordinates to 0.25° grid and hourly bucket for high cache reuse."""
    grid_lat = round(lat * 4.0) / 4.0
    grid_lon = round(lon * 4.0) / 4.0
    return (grid_lat, grid_lon, dt_utc.strftime("%Y-%m-%dT%H"))


def _get_climatological_wind(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float]:
    """
    Provides a realistic seasonal Indian Ocean monsoon regime baseline when remote API is throttled.
    - Southwest Monsoon (May - Sept): Strong SW/WSW winds (15-20 kn) across Arabian Sea & Bay of Bengal.
    - Northeast Monsoon (Nov - Feb): Moderate NE winds (10-14 kn).
    - Inter-monsoon transitions (March-April, October): Moderate NW/variable winds (8-10 kn).
    """
    month = dt_utc.month
    if 5 <= month <= 9:
        speed = 18.0 if (10.0 <= lat <= 22.0) else 14.0
        direction = 245.0  # From WSW (245°)
    elif 11 <= month or month <= 2:
        speed = 12.0
        direction = 45.0   # From NE (45°)
    else:
        speed = 9.0
        direction = 310.0  # From NW (310°)
    return (speed, direction)


class OpenMeteoWindProvider(WeatherProvider):
    """
    Atmospheric weather provider fetching 10-meter surface wind forecasts from Open-Meteo.

    Data Flow:
        Open-Meteo Forecast API (wind_speed_10m, wind_direction_10m) ──► EnvironmentalData (Wind Only)

    Attributes:
        api_url: Open-Meteo weather forecast endpoint URL.
        timeout: Network request timeout in seconds.
        enable_cache: Enables in-memory caching of fetched observations.
    """

    DEFAULT_API_URL: str = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        timeout: float = 3.0,
        enable_cache: bool = True,
        fetcher_fn: Optional[Callable[[str, float], Dict[str, Any]]] = None,
    ) -> None:
        """
        Initializes the Open-Meteo atmospheric wind provider.

        Args:
            api_url: Open-Meteo forecast endpoint URL.
            timeout: HTTP request timeout in seconds (default: 3.0s).
            enable_cache: When True, caches spatial/temporal queries in memory.
            fetcher_fn: Optional callable for fetching raw JSON (used for dependency injection / offline testing).
        """
        self.api_url = api_url
        self.timeout = timeout
        self.enable_cache = enable_cache
        self._fetcher_fn = fetcher_fn
        # In test mode with injected fetcher, use clean instance cache for isolation.
        # In production mode (no injected fetcher), use global cache to retain forecast across requests.
        self._cache = {} if fetcher_fn is not None else _GLOBAL_WIND_CACHE

    def _default_http_fetcher(self, url: str, timeout: float) -> Dict[str, Any]:
        """Fetches JSON payload over HTTP using urllib.request with timeout, retry backoff, and error handling."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NauDisha-Ship-Routing-System/0.1.0 (Academic/Research Project)",
                "Accept": "application/json",
            },
        )
        max_retries = 3
        backoff_seconds = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.status != 200:
                        raise WindNetworkError(f"Open-Meteo returned non-200 HTTP status: {response.status}")
                    raw_data = response.read().decode("utf-8")
                    return json.loads(raw_data)
            except urllib.error.HTTPError as http_err:
                if http_err.code == 429:
                    raise WindNetworkError(f"Open-Meteo rate limit (429): {http_err.reason}") from http_err
                if http_err.code in (500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(0.2)
                    continue
                raise WindNetworkError(f"HTTP error ({http_err.code}) querying Open-Meteo: {http_err.reason}") from http_err
            except (urllib.error.URLError, TimeoutError) as net_err:
                if attempt < max_retries:
                    time.sleep(0.2)
                    continue
                raise WindNetworkError(f"Network error communicating with Open-Meteo: {net_err}") from net_err
            except json.JSONDecodeError as json_err:
                raise WindResponseMalformedError(f"Invalid JSON payload returned by Open-Meteo: {json_err}") from json_err
            except Exception as exc:
                raise WindProviderError(f"Unexpected error during Open-Meteo request: {exc}") from exc

    def _get_fetcher(self) -> Callable[[str, float], Dict[str, Any]]:
        """Returns the active HTTP fetcher (injected fetcher or default urllib fetcher)."""
        return self._fetcher_fn if self._fetcher_fn is not None else self._default_http_fetcher

    def _find_nearest_hourly_index(self, target_dt: datetime, time_strings: List[str]) -> int:
        """Finds the index of the nearest hourly timestamp in the Open-Meteo time array."""
        if not time_strings:
            raise WindDataUnavailableError("Empty time array returned in Open-Meteo response.")

        best_index = -1
        min_delta = timedelta.max

        for i, time_str in enumerate(time_strings):
            # Open-Meteo hourly times format: "2026-08-16T12:00"
            entry_dt = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
            delta = abs(target_dt - entry_dt)
            if delta < min_delta:
                min_delta = delta
                best_index = i

        if best_index == -1:
            raise WindDataUnavailableError(f"Could not locate matching timestamp for {target_dt.isoformat()}.")

        return best_index

    def _parse_single_hourly_payload(
        self,
        payload: Dict[str, Any],
        dt_utc: datetime,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Parses wind speed (kn) and wind direction (deg) from one location's hourly payload."""
        if not isinstance(payload, dict):
            raise WindResponseMalformedError(f"Expected JSON dictionary payload, got {type(payload)}.")

        if "error" in payload and payload["error"]:
            reason = payload.get("reason", "Unknown Open-Meteo error")
            raise WindDataUnavailableError(f"Open-Meteo API returned error: {reason}")

        if "hourly" not in payload:
            raise WindResponseMalformedError("Missing 'hourly' section in Open-Meteo response.")

        hourly = payload["hourly"]
        for required_key in ("time", "wind_speed_10m", "wind_direction_10m"):
            if required_key not in hourly:
                raise WindResponseMalformedError(f"Missing required hourly field '{required_key}' in response.")

        time_list = hourly["time"]
        speed_list = hourly["wind_speed_10m"]
        direction_list = hourly["wind_direction_10m"]

        if not time_list or not speed_list or not direction_list:
            loc_str = f" for ({lat:.4f}N, {lon:.4f}E)" if lat is not None and lon is not None else ""
            raise WindDataUnavailableError(f"Empty data arrays returned{loc_str}.")

        idx = self._find_nearest_hourly_index(dt_utc, time_list)

        raw_speed = speed_list[idx]
        raw_direction = direction_list[idx]

        if raw_speed is None or raw_direction is None or math.isnan(raw_speed) or math.isnan(raw_direction):
            loc_str = f" for ({lat:.4f}N, {lon:.4f}E)" if lat is not None and lon is not None else ""
            raise WindDataUnavailableError(f"Null or NaN wind values returned at index {idx}{loc_str}.")

        hourly_units = payload.get("hourly_units", {})
        speed_unit = hourly_units.get("wind_speed_10m", "kn").lower()

        if speed_unit == "kn":
            wind_speed_knots = float(raw_speed)
        elif speed_unit in ("km/h", "kmh"):
            wind_speed_knots = float(raw_speed) * KMH_TO_KNOTS
        elif speed_unit in ("m/s", "ms"):
            wind_speed_knots = float(raw_speed) * MS_TO_KNOTS
        else:
            wind_speed_knots = float(raw_speed)

        wind_direction_deg = float(raw_direction) % 360.0
        return (wind_speed_knots, wind_direction_deg)

    def fetch_wind(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> Tuple[float, float]:
        """
        Fetches wind speed (knots) and wind direction (degrees) at specified coordinates and timestamp.

        Args:
            lat: Latitude in degrees [-90.0, 90.0].
            lon: Longitude in degrees [-180.0, 180.0].
            timestamp: Observation/forecast timestamp.

        Returns:
            (wind_speed_knots, wind_direction_degrees)
        """
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude {lat} is out of valid range [-90.0, 90.0].")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude {lon} is out of valid range [-180.0, 180.0].")

        dt_utc = _normalize_utc_datetime(timestamp)
        cache_key = _to_cache_key(lat, lon, dt_utc)

        if self.enable_cache and cache_key in self._cache:
            logger.debug("Returning cached wind conditions for key %s", cache_key)
            return self._cache[cache_key]

        # Construct Open-Meteo forecast API query parameters
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": "wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "kn",
            "timezone": "UTC",
        }
        query_url = f"{self.api_url}?{urllib.parse.urlencode(params)}"

        fetcher = self._get_fetcher()
        payload = fetcher(query_url, self.timeout)
        res = self._parse_single_hourly_payload(payload, dt_utc, lat=lat, lon=lon)

        if self.enable_cache:
            self._cache[cache_key] = res

        return res

    def fetch_wind_batch(
        self,
        requests: Sequence[Any],
    ) -> Dict[Any, Tuple[float, float]]:
        """
        Fetches wind speed and direction for multiple points using Open-Meteo's native
        multi-location batch capability (comma-separated coordinates in 1 HTTP request).

        Args:
            requests: Sequence of ConditionRequest objects or objects with lat, lon, timestamp attributes.

        Returns:
            Dict mapping each request object to (wind_speed_knots, wind_direction_deg).
        """
        if not requests:
            return {}

        results: Dict[Any, Tuple[float, float]] = {}
        uncached_reqs: List[Any] = []

        # 1. Check cache first
        for req in requests:
            if not (-90.0 <= req.lat <= 90.0):
                raise ValueError(f"Latitude {req.lat} is out of valid range [-90.0, 90.0].")
            if not (-180.0 <= req.lon <= 180.0):
                raise ValueError(f"Longitude {req.lon} is out of valid range [-180.0, 180.0].")

            dt_utc = _normalize_utc_datetime(req.timestamp)
            cache_key = _to_cache_key(req.lat, req.lon, dt_utc)
            if self.enable_cache and cache_key in self._cache:
                results[req] = self._cache[cache_key]
            else:
                uncached_reqs.append(req)

        if not uncached_reqs:
            return results

        # 2. Deduplicate unique cells to query
        unique_cells: Dict[Tuple[float, float, str], Any] = {}
        for req in uncached_reqs:
            dt_utc = _normalize_utc_datetime(req.timestamp)
            cell_key = _to_cache_key(req.lat, req.lon, dt_utc)
            if cell_key not in unique_cells:
                unique_cells[cell_key] = req

        unique_req_list = list(unique_cells.values())

        # 3. Query in chunks of up to 50 locations per single HTTP request (parallelized across chunks)
        from concurrent.futures import ThreadPoolExecutor
        chunk_size = 50
        chunks = [unique_req_list[i : i + chunk_size] for i in range(0, len(unique_req_list), chunk_size)]
        batch_parsed: Dict[Tuple[float, float, str], Tuple[float, float]] = {}

        def _fetch_single_chunk(chunk: List[Any]) -> Dict[Tuple[float, float, str], Tuple[float, float]]:
            chunk_results: Dict[Tuple[float, float, str], Tuple[float, float]] = {}
            lats_str = ",".join(f"{r.lat:.4f}" for r in chunk)
            lons_str = ",".join(f"{r.lon:.4f}" for r in chunk)

            params = {
                "latitude": lats_str,
                "longitude": lons_str,
                "hourly": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "kn",
                "timezone": "UTC",
            }
            query_url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
            try:
                fetcher = self._get_fetcher()
                payload = fetcher(query_url, self.timeout)

                # When len(chunk) == 1, payload is a single dict; when len(chunk) > 1, payload is list[dict]
                if isinstance(payload, list):
                    payload_list = payload
                elif isinstance(payload, dict):
                    payload_list = [payload]
                else:
                    raise WindResponseMalformedError(f"Expected dict or list from Open-Meteo, got {type(payload)}.")

                for r, loc_payload in zip(chunk, payload_list):
                    dt_utc = _normalize_utc_datetime(r.timestamp)
                    cell_key = _to_cache_key(r.lat, r.lon, dt_utc)
                    parsed = self._parse_single_hourly_payload(loc_payload, dt_utc, lat=r.lat, lon=r.lon)
                    chunk_results[cell_key] = parsed
            except Exception as exc:
                logger.warning("Open-Meteo batch wind fetch failed (%s), defaulting to seasonal monsoon model.", exc)
                for r in chunk:
                    dt_utc = _normalize_utc_datetime(r.timestamp)
                    cell_key = _to_cache_key(r.lat, r.lon, dt_utc)
                    chunk_results[cell_key] = _get_climatological_wind(r.lat, r.lon, dt_utc)
            return chunk_results

        if len(chunks) == 1:
            res = _fetch_single_chunk(chunks[0])
            batch_parsed.update(res)
        elif len(chunks) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(chunks)), thread_name_prefix="om_chunk") as pool:
                futures = [pool.submit(_fetch_single_chunk, chunk) for chunk in chunks]
                for fut in futures:
                    batch_parsed.update(fut.result())

        if self.enable_cache:
            for cell_key, val in batch_parsed.items():
                self._cache[cell_key] = val

        # 4. Populate results for all uncached requests
        for req in uncached_reqs:
            dt_utc = _normalize_utc_datetime(req.timestamp)
            cell_key = _to_cache_key(req.lat, req.lon, dt_utc)
            if cell_key in batch_parsed:
                results[req] = batch_parsed[cell_key]
            elif cell_key in self._cache:
                results[req] = self._cache[cell_key]
            else:
                results[req] = _get_climatological_wind(req.lat, req.lon, dt_utc)

        return results

    def fetch_conditions(
        self,
        lat: float,
        lon: float,
        timestamp: Union[datetime, str],
    ) -> EnvironmentalData:
        """
        Fetches atmospheric wind conditions and maps them into an EnvironmentalData model.

        Wave and current fields are set to None as they are provided by Copernicus Marine.

        Args:
            lat: Latitude in degrees [-90.0, 90.0].
            lon: Longitude in degrees [-180.0, 180.0].
            timestamp: Observation/forecast timestamp.

        Returns:
            EnvironmentalData object with wind fields populated.
        """
        dt_utc = _normalize_utc_datetime(timestamp)
        wind_speed, wind_direction = self.fetch_wind(lat=lat, lon=lon, timestamp=dt_utc)

        return EnvironmentalData(
            timestamp=dt_utc.isoformat(),
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            wave_height=None,
            wave_direction=None,
            wave_period=None,
            current_speed=None,
            current_direction=None,
        )
