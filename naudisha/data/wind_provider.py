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
        timeout: float = 10.0,
        enable_cache: bool = True,
        fetcher_fn: Optional[Callable[[str, float], Dict[str, Any]]] = None,
    ) -> None:
        """
        Initializes the Open-Meteo atmospheric wind provider.

        Args:
            api_url: Open-Meteo forecast endpoint URL.
            timeout: HTTP request timeout in seconds (default: 10.0s).
            enable_cache: When True, caches spatial/temporal queries in memory.
            fetcher_fn: Optional callable for fetching raw JSON (used for dependency injection / offline testing).
        """
        self.api_url = api_url
        self.timeout = timeout
        self.enable_cache = enable_cache
        self._fetcher_fn = fetcher_fn
        self._cache: Dict[Tuple[float, float, str], Tuple[float, float]] = {}

    def _default_http_fetcher(self, url: str, timeout: float) -> Dict[str, Any]:
        """Fetches JSON payload over HTTP using urllib.request with timeout and error handling."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NauDisha-Ship-Routing-System/0.1.0 (Academic/Research Project)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise WindNetworkError(f"Open-Meteo returned non-200 HTTP status: {response.status}")
                raw_data = response.read().decode("utf-8")
                return json.loads(raw_data)
        except urllib.error.HTTPError as http_err:
            raise WindNetworkError(f"HTTP error ({http_err.code}) querying Open-Meteo: {http_err.reason}") from http_err
        except urllib.error.URLError as url_err:
            raise WindNetworkError(f"Network error communicating with Open-Meteo: {url_err.reason}") from url_err
        except TimeoutError as to_err:
            raise WindNetworkError(f"Timeout ({timeout}s) exceeded querying Open-Meteo.") from to_err
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
        cache_key = (round(lat, 2), round(lon, 2), dt_utc.strftime("%Y-%m-%dT%H"))

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

        # Validate response payload structure
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
            raise WindDataUnavailableError(f"Empty data arrays returned for coordinates ({lat:.4f}N, {lon:.4f}E).")

        idx = self._find_nearest_hourly_index(dt_utc, time_list)

        raw_speed = speed_list[idx]
        raw_direction = direction_list[idx]

        if raw_speed is None or raw_direction is None or math.isnan(raw_speed) or math.isnan(raw_direction):
            raise WindDataUnavailableError(
                f"Null or NaN wind values returned at index {idx} for ({lat:.4f}N, {lon:.4f}E)."
            )

        # Check units returned by API metadata
        hourly_units = payload.get("hourly_units", {})
        speed_unit = hourly_units.get("wind_speed_10m", "kn").lower()

        if speed_unit == "kn":
            wind_speed_knots = float(raw_speed)
        elif speed_unit in ("km/h", "kmh"):
            wind_speed_knots = float(raw_speed) * KMH_TO_KNOTS
        elif speed_unit in ("m/s", "ms"):
            wind_speed_knots = float(raw_speed) * MS_TO_KNOTS
        else:
            # Fallback to direct value if already in knots
            wind_speed_knots = float(raw_speed)

        wind_direction_deg = float(raw_direction) % 360.0

        if self.enable_cache:
            self._cache[cache_key] = (wind_speed_knots, wind_direction_deg)

        return (wind_speed_knots, wind_direction_deg)

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
