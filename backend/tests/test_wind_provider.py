"""
Offline unit tests for OpenMeteoWindProvider.
Tests wind forecast parsing, unit conversions, timestamp selection, cache mechanics,
and error handling using mock HTTP fetchers without network access.
"""

import unittest
from datetime import datetime, timezone

from naudisha.data.wind_provider import (
    OpenMeteoWindProvider,
    WindProviderError,
    WindNetworkError,
    WindDataUnavailableError,
    WindResponseMalformedError,
    KMH_TO_KNOTS,
    MS_TO_KNOTS,
)


class TestOpenMeteoWindProvider(unittest.TestCase):
    """Test suite for OpenMeteoWindProvider using mock JSON fetchers."""

    def setUp(self):
        self.sample_lat = 18.50
        self.sample_lon = 72.00
        self.sample_time = "2026-08-16T12:00:00Z"

        # Standard sample response from Open-Meteo
        self.valid_response_payload = {
            "latitude": 18.5,
            "longitude": 72.0,
            "timezone": "UTC",
            "hourly_units": {
                "time": "iso8601",
                "wind_speed_10m": "kn",
                "wind_direction_10m": "°",
            },
            "hourly": {
                "time": [
                    "2026-08-16T10:00",
                    "2026-08-16T11:00",
                    "2026-08-16T12:00",
                    "2026-08-16T13:00",
                ],
                "wind_speed_10m": [12.0, 14.5, 16.8, 15.2],
                "wind_direction_10m": [220.0, 230.0, 245.0, 250.0],
            },
        }

    def test_successful_wind_parsing_and_mapping(self):
        """Tests that wind speed (knots) and wind direction (degrees) are parsed and mapped into EnvironmentalData."""
        recorded_urls = []

        def mock_fetcher(url, timeout):
            recorded_urls.append(url)
            return self.valid_response_payload

        provider = OpenMeteoWindProvider(fetcher_fn=mock_fetcher)
        env = provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

        # 1. Verify query URL constructed
        self.assertEqual(len(recorded_urls), 1)
        self.assertIn("latitude=18.5000", recorded_urls[0])
        self.assertIn("longitude=72.0000", recorded_urls[0])
        self.assertIn("wind_speed_unit=kn", recorded_urls[0])

        # 2. Verify EnvironmentalData values
        self.assertAlmostEqual(env.wind_speed, 16.8)
        self.assertAlmostEqual(env.wind_direction, 245.0)
        self.assertIsNone(env.wave_height)
        self.assertIsNone(env.wave_direction)
        self.assertIsNone(env.wave_period)
        self.assertIsNone(env.current_speed)
        self.assertIsNone(env.current_direction)

    def test_nearest_timestamp_selection(self):
        """Tests that nearest hourly slice is chosen for arbitrary sub-hour timestamps."""
        def mock_fetcher(url, timeout):
            return self.valid_response_payload

        provider = OpenMeteoWindProvider(fetcher_fn=mock_fetcher)

        # 11:45 UTC should match 12:00 UTC (16.8 kn) rather than 11:00 UTC (14.5 kn)
        speed, direction = provider.fetch_wind(self.sample_lat, self.sample_lon, "2026-08-16T11:45:00Z")
        self.assertAlmostEqual(speed, 16.8)
        self.assertAlmostEqual(direction, 245.0)

        # 10:15 UTC should match 10:00 UTC (12.0 kn)
        speed_early, _ = provider.fetch_wind(self.sample_lat, self.sample_lon, "2026-08-16T10:15:00Z")
        self.assertAlmostEqual(speed_early, 12.0)

    def test_unit_conversions(self):
        """Tests that speed units in km/h or m/s are accurately converted to knots."""
        # 1. Test km/h conversion
        payload_kmh = {
            "hourly_units": {"wind_speed_10m": "km/h"},
            "hourly": {
                "time": ["2026-08-16T12:00"],
                "wind_speed_10m": [30.0],  # 30 km/h
                "wind_direction_10m": [180.0],
            },
        }
        provider_kmh = OpenMeteoWindProvider(fetcher_fn=lambda url, to: payload_kmh)
        speed_kmh, _ = provider_kmh.fetch_wind(18.5, 72.0, self.sample_time)
        self.assertAlmostEqual(speed_kmh, 30.0 * KMH_TO_KNOTS, places=4)

        # 2. Test m/s conversion
        payload_ms = {
            "hourly_units": {"wind_speed_10m": "m/s"},
            "hourly": {
                "time": ["2026-08-16T12:00"],
                "wind_speed_10m": [10.0],  # 10 m/s
                "wind_direction_10m": [90.0],
            },
        }
        provider_ms = OpenMeteoWindProvider(fetcher_fn=lambda url, to: payload_ms)
        speed_ms, _ = provider_ms.fetch_wind(18.5, 72.0, self.sample_time)
        self.assertAlmostEqual(speed_ms, 10.0 * MS_TO_KNOTS, places=4)

    def test_in_memory_cache_hit(self):
        """Tests that duplicate requests for the same cell and hour do not hit the HTTP fetcher."""
        call_count = 0

        def mock_fetcher(url, timeout):
            nonlocal call_count
            call_count += 1
            return self.valid_response_payload

        provider = OpenMeteoWindProvider(fetcher_fn=mock_fetcher, enable_cache=True)

        w1 = provider.fetch_wind(18.50, 72.00, "2026-08-16T12:00:00Z")
        self.assertEqual(call_count, 1)

        # Sub-hour timestamp in same cell hits cache
        w2 = provider.fetch_wind(18.50, 72.00, "2026-08-16T12:25:00Z")
        self.assertEqual(call_count, 1)
        self.assertEqual(w1, w2)

    def test_missing_and_nan_values_raise_error(self):
        """Tests that null/NaN arrays trigger WindDataUnavailableError."""
        payload_nan = {
            "hourly_units": {"wind_speed_10m": "kn"},
            "hourly": {
                "time": ["2026-08-16T12:00"],
                "wind_speed_10m": [float("nan")],
                "wind_direction_10m": [180.0],
            },
        }
        provider = OpenMeteoWindProvider(fetcher_fn=lambda u, t: payload_nan)
        with self.assertRaises(WindDataUnavailableError):
            provider.fetch_wind(18.5, 72.0, self.sample_time)

    def test_malformed_response_schema_raises_error(self):
        """Tests that missing required JSON schema sections raise WindResponseMalformedError."""
        # 1. Missing 'hourly'
        provider1 = OpenMeteoWindProvider(fetcher_fn=lambda u, t: {"latitude": 18.5})
        with self.assertRaises(WindResponseMalformedError):
            provider1.fetch_wind(18.5, 72.0, self.sample_time)

        # 2. Missing 'wind_speed_10m' in hourly
        provider2 = OpenMeteoWindProvider(
            fetcher_fn=lambda u, t: {"hourly": {"time": ["2026-08-16T12:00"], "wind_direction_10m": [180.0]}}
        )
        with self.assertRaises(WindResponseMalformedError):
            provider2.fetch_wind(18.5, 72.0, self.sample_time)

    def test_network_and_http_error_handling(self):
        """Tests that network/HTTP exceptions are properly converted into WindNetworkError."""
        def failing_fetcher(url, timeout):
            raise WindNetworkError("Connection timed out")

        provider = OpenMeteoWindProvider(fetcher_fn=failing_fetcher)
        with self.assertRaises(WindNetworkError):
            provider.fetch_wind(18.5, 72.0, self.sample_time)

    def test_coordinate_bounds_validation(self):
        """Tests that invalid lat/lon bounds raise ValueError."""
        provider = OpenMeteoWindProvider(fetcher_fn=lambda u, t: self.valid_response_payload)

        with self.assertRaises(ValueError):
            provider.fetch_wind(95.0, 72.0, self.sample_time)

        with self.assertRaises(ValueError):
            provider.fetch_wind(18.0, 195.0, self.sample_time)


if __name__ == "__main__":
    unittest.main()
