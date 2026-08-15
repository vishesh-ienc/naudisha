"""
Offline unit tests for CopernicusMarineProvider.
Uses mock data readers to test all provider mechanics, query construction, data mapping,
and error handling without network access or live credentials.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pandas as pd

from naudisha.data.copernicus_provider import (
    CopernicusMarineProvider,
    CopernicusProviderError,
    CopernicusAuthenticationError,
    CopernicusDataUnavailableError,
)
from naudisha.data.copernicus_schema import (
    CMEMS_OCEAN_CURRENTS_SPEC,
    CMEMS_WAVES_SPEC,
    convert_current_vectors_to_speed_and_direction,
)


class TestCopernicusMarineProvider(unittest.TestCase):
    """Test suite for CopernicusMarineProvider using dependency-injected mock reader."""

    def setUp(self):
        self.sample_lat = 18.9220
        self.sample_lon = 72.8347
        self.sample_time = "2026-08-16T12:00:00Z"

    def test_successful_fetch_and_mapping(self):
        """Tests that currents (uo, vo) and wave variables are fetched and mapped into EnvironmentalData."""
        recorded_queries = []

        def mock_reader(**kwargs):
            recorded_queries.append(kwargs)
            dataset_id = kwargs["dataset_id"]
            if dataset_id == CMEMS_OCEAN_CURRENTS_SPEC.dataset_id:
                return pd.DataFrame({
                    "uo": [0.40],
                    "vo": [0.30],
                    "latitude": [18.9],
                    "longitude": [72.8],
                })
            elif dataset_id == CMEMS_WAVES_SPEC.dataset_id:
                return pd.DataFrame({
                    "VHM0": [2.5],
                    "VMDR": [210.0],
                    "VTPK": [8.0],
                    "latitude": [18.9],
                    "longitude": [72.8],
                })
            return pd.DataFrame()

        provider = CopernicusMarineProvider(reader_fn=mock_reader, enable_cache=True)
        env = provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

        # 1. Verify queries constructed
        self.assertEqual(len(recorded_queries), 2)
        cur_q = recorded_queries[0]
        self.assertEqual(cur_q["dataset_id"], CMEMS_OCEAN_CURRENTS_SPEC.dataset_id)
        self.assertEqual(cur_q["variables"], ["uo", "vo"])
        self.assertEqual(cur_q["coordinates_selection_method"], "nearest")

        wav_q = recorded_queries[1]
        self.assertEqual(wav_q["dataset_id"], CMEMS_WAVES_SPEC.dataset_id)
        self.assertEqual(wav_q["variables"], ["VHM0", "VMDR", "VTPK"])

        # 2. Verify EnvironmentalData mapping
        self.assertIsNone(env.wind_speed)
        self.assertIsNone(env.wind_direction)
        self.assertEqual(env.wave_height, 2.5)
        self.assertEqual(env.wave_direction, 210.0)
        self.assertEqual(env.wave_period, 8.0)

        expected_speed, expected_dir = convert_current_vectors_to_speed_and_direction(0.40, 0.30)
        self.assertAlmostEqual(env.current_speed, expected_speed, places=4)
        self.assertAlmostEqual(env.current_direction, expected_dir, places=4)

    def test_in_memory_cache_hit(self):
        """Tests that subsequent requests for the same coordinate/hour return cached EnvironmentalData."""
        call_count = 0

        def mock_reader(**kwargs):
            nonlocal call_count
            call_count += 1
            if "phy" in kwargs["dataset_id"]:
                return pd.DataFrame({"uo": [0.2], "vo": [0.2]})
            return pd.DataFrame({"VHM0": [1.5], "VMDR": [90.0], "VTPK": [6.0]})

        provider = CopernicusMarineProvider(reader_fn=mock_reader, enable_cache=True)

        # First fetch triggers 2 queries (currents + waves)
        env1 = provider.fetch_conditions(18.9, 72.8, "2026-08-16T12:00:00Z")
        self.assertEqual(call_count, 2)

        # Second fetch for same cell and hour hits cache
        env2 = provider.fetch_conditions(18.9, 72.8, "2026-08-16T12:15:00Z")
        self.assertEqual(call_count, 2)
        self.assertEqual(env1.current_speed, env2.current_speed)

    def test_missing_current_values_raises_error(self):
        """Tests that empty current DataFrame raises CopernicusDataUnavailableError."""
        def mock_reader(**kwargs):
            if "phy" in kwargs["dataset_id"]:
                return pd.DataFrame()  # Empty
            return pd.DataFrame({"VHM0": [1.5], "VMDR": [90.0], "VTPK": [6.0]})

        provider = CopernicusMarineProvider(reader_fn=mock_reader)
        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

    def test_nan_current_values_raises_error(self):
        """Tests that all-NaN current columns raise CopernicusDataUnavailableError."""
        def mock_reader(**kwargs):
            if "phy" in kwargs["dataset_id"]:
                return pd.DataFrame({"uo": [float("nan")], "vo": [0.5]})
            return pd.DataFrame({"VHM0": [1.5], "VMDR": [90.0], "VTPK": [6.0]})

        provider = CopernicusMarineProvider(reader_fn=mock_reader)
        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

    def test_missing_wave_values_raises_error(self):
        """Tests that empty wave response raises CopernicusDataUnavailableError."""
        def mock_reader(**kwargs):
            if "phy" in kwargs["dataset_id"]:
                return pd.DataFrame({"uo": [0.5], "vo": [0.5]})
            return pd.DataFrame({"VHM0": [1.0]})  # Missing VMDR and VTPK

        provider = CopernicusMarineProvider(reader_fn=mock_reader)
        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

    def test_authentication_error_handling(self):
        """Tests that credential/authentication exceptions from reader are translated into CopernicusAuthenticationError."""
        def mock_reader(**kwargs):
            raise Exception("Unauthorized: Invalid username or password in credentials file")

        provider = CopernicusMarineProvider(reader_fn=mock_reader)
        with self.assertRaises(CopernicusAuthenticationError):
            provider.fetch_conditions(self.sample_lat, self.sample_lon, self.sample_time)

    def test_coordinate_bounds_validation(self):
        """Tests that out-of-range coordinates raise ValueError immediately."""
        provider = CopernicusMarineProvider(reader_fn=lambda **kw: pd.DataFrame())

        with self.assertRaises(ValueError):
            provider.fetch_conditions(95.0, 72.0, self.sample_time)  # Lat > 90

        with self.assertRaises(ValueError):
            provider.fetch_conditions(18.0, 195.0, self.sample_time)  # Lon > 180


if __name__ == "__main__":
    unittest.main()
