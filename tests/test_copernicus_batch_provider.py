"""
Offline unit tests for CopernicusMarineProvider batch fetching and GeographicGridGraph
batch-population integration.

All tests are completely offline. No network access. All CMEMS calls use injected reader_fn.

Test count: 20 (18 provider tests + 2 graph integration tests)
"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from naudisha.core.models import (
    ShipProfile,
    EnvironmentalData,
    CostWeights,
)
from naudisha.data.weather_provider import (
    WeatherProvider,
    BatchCapableProvider,
    ConditionRequest,
)
from naudisha.data.copernicus_provider import (
    CopernicusMarineProvider,
    CopernicusProviderError,
    CopernicusAuthenticationError,
    CopernicusDataUnavailableError,
)
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
    GridEnvironmentUpdateError,
)
from naudisha.routing.dstar_lite import DStarLite


# ---------------------------------------------------------------------------
# DataFrame factory helpers
# ---------------------------------------------------------------------------

def make_currents_df(
    rows: List[Dict[str, float]],
    include_spatial: bool = True,
) -> pd.DataFrame:
    """
    Creates a fake CMEMS currents DataFrame with columns: latitude, longitude, uo, vo.
    Mirrors the real copernicusmarine.read_dataframe output schema.
    """
    if include_spatial:
        return pd.DataFrame(rows, columns=["latitude", "longitude", "uo", "vo"])
    else:
        return pd.DataFrame(rows, columns=["uo", "vo"])


def make_waves_df(
    rows: List[Dict[str, float]],
    include_spatial: bool = True,
) -> pd.DataFrame:
    """
    Creates a fake CMEMS waves DataFrame with columns: latitude, longitude, VHM0, VMDR, VTPK.
    """
    if include_spatial:
        return pd.DataFrame(rows, columns=["latitude", "longitude", "VHM0", "VMDR", "VTPK"])
    else:
        return pd.DataFrame(rows, columns=["VHM0", "VMDR", "VTPK"])


# ---------------------------------------------------------------------------
# Fake reader factory
# ---------------------------------------------------------------------------

class FakeBatchReader:
    """
    Fake reader_fn for offline testing. Returns pre-registered DataFrames keyed by dataset_id.
    Records every call for request-count verification.
    """

    def __init__(self) -> None:
        self.responses: Dict[str, pd.DataFrame] = {}
        self.call_log: List[Dict] = []

    def register(self, dataset_id: str, df: pd.DataFrame) -> None:
        self.responses[dataset_id] = df

    def __call__(self, **kwargs) -> pd.DataFrame:
        dataset_id = kwargs.get("dataset_id", "")
        self.call_log.append(kwargs)
        if dataset_id not in self.responses:
            raise RuntimeError(f"No registered response for dataset '{dataset_id}'.")
        return self.responses[dataset_id]

    @property
    def call_count(self) -> int:
        return len(self.call_log)


# ---------------------------------------------------------------------------
# Standard test fixtures
# ---------------------------------------------------------------------------

CURRENTS_DATASET = "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i"
WAVES_DATASET = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

POINT_A = (18.125, 70.625)  # midpoint of edge node_0_0 -> node_0_1 on a 5x5 grid
POINT_B = (18.375, 70.875)
POINT_C = (17.875, 71.125)
TIMESTAMP = "2026-08-15T12:00:00Z"


def make_provider_with_reader(reader: FakeBatchReader) -> CopernicusMarineProvider:
    return CopernicusMarineProvider(
        enable_cache=False,
        reader_fn=reader,
        spatial_delta_deg=0.1,
        temporal_delta_hours=3.0,
    )


def make_standard_currents_df() -> pd.DataFrame:
    """Multi-row currents DataFrame covering POINT_A, POINT_B, POINT_C."""
    return make_currents_df([
        {"latitude": 18.125, "longitude": 70.625, "uo": 0.15, "vo": 0.08},
        {"latitude": 18.375, "longitude": 70.875, "uo": -0.05, "vo": 0.20},
        {"latitude": 17.875, "longitude": 71.125, "uo": 0.30, "vo": -0.10},
    ])


def make_standard_waves_df() -> pd.DataFrame:
    """Multi-row waves DataFrame covering POINT_A, POINT_B, POINT_C."""
    return make_waves_df([
        {"latitude": 18.125, "longitude": 70.625, "VHM0": 2.1, "VMDR": 240.0, "VTPK": 8.5},
        {"latitude": 18.375, "longitude": 70.875, "VHM0": 1.8, "VMDR": 255.0, "VTPK": 7.0},
        {"latitude": 17.875, "longitude": 71.125, "VHM0": 2.5, "VMDR": 230.0, "VTPK": 9.0},
    ])


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestCopernicusBatchProvider(unittest.TestCase):
    """
    Offline unit tests for CopernicusMarineProvider batch fetch capability.
    All CMEMS calls use injected reader_fn — no network access.
    """

    def _make_reader_and_provider(self) -> Tuple[FakeBatchReader, CopernicusMarineProvider]:
        reader = FakeBatchReader()
        provider = make_provider_with_reader(reader)
        reader.register(CURRENTS_DATASET, make_standard_currents_df())
        reader.register(WAVES_DATASET, make_standard_waves_df())
        return reader, provider

    # -----------------------------------------------------------------------
    # 1. ConditionRequest dataclass creation
    # -----------------------------------------------------------------------

    def test_01_condition_request_dataclass(self):
        """1. ConditionRequest is a frozen dataclass, hashable, and usable as dict key."""
        req = ConditionRequest(lat=18.0, lon=72.0, timestamp=TIMESTAMP)
        self.assertEqual(req.lat, 18.0)
        self.assertEqual(req.lon, 72.0)
        self.assertEqual(req.timestamp, TIMESTAMP)
        # Must be hashable (frozen dataclass)
        d = {req: "value"}
        self.assertEqual(d[req], "value")

    # -----------------------------------------------------------------------
    # 2. Bounding box calculation
    # -----------------------------------------------------------------------

    def test_02_bounding_box_calculation(self):
        """2. Batch query bounding box = min/max(lats/lons) +/- spatial_delta_deg."""
        reader = FakeBatchReader()
        reader.register(CURRENTS_DATASET, make_standard_currents_df())
        reader.register(WAVES_DATASET, make_standard_waves_df())
        provider = CopernicusMarineProvider(
            enable_cache=False, reader_fn=reader, spatial_delta_deg=0.1, temporal_delta_hours=3.0
        )
        requests = [
            ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP),
            ConditionRequest(lat=18.375, lon=70.875, timestamp=TIMESTAMP),
            ConditionRequest(lat=17.875, lon=71.125, timestamp=TIMESTAMP),
        ]
        provider.fetch_conditions_batch(requests)

        # Check the kwargs passed to reader for currents call
        cur_call = next(c for c in reader.call_log if c["dataset_id"] == CURRENTS_DATASET)
        self.assertAlmostEqual(cur_call["minimum_latitude"], 17.875 - 0.1, places=6)
        self.assertAlmostEqual(cur_call["maximum_latitude"], 18.375 + 0.1, places=6)
        self.assertAlmostEqual(cur_call["minimum_longitude"], 70.625 - 0.1, places=6)
        self.assertAlmostEqual(cur_call["maximum_longitude"], 71.125 + 0.1, places=6)

    # -----------------------------------------------------------------------
    # 3. Temporal range calculation
    # -----------------------------------------------------------------------

    def test_03_temporal_range_calculation(self):
        """3. Temporal range covers [bucket_dt - delta_h, bucket_dt + delta_h]."""
        reader, provider = self._make_reader_and_provider()
        requests = [ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)]
        provider.fetch_conditions_batch(requests)

        cur_call = reader.call_log[0]
        start = datetime.fromisoformat(cur_call["start_datetime"])
        end = datetime.fromisoformat(cur_call["end_datetime"])
        bucket_dt = datetime(2026, 8, 15, 12, 0, 0)
        self.assertEqual(start, bucket_dt - timedelta(hours=3.0))
        self.assertEqual(end, bucket_dt + timedelta(hours=3.0))

    # -----------------------------------------------------------------------
    # 4. ONE currents request for N points (same timestamp)
    # -----------------------------------------------------------------------

    def test_04_one_currents_request_for_n_points(self):
        """4. All points sharing the same timestamp-hour use exactly 1 currents reader call."""
        reader, provider = self._make_reader_and_provider()
        requests = [
            ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP),
            ConditionRequest(lat=18.375, lon=70.875, timestamp=TIMESTAMP),
            ConditionRequest(lat=17.875, lon=71.125, timestamp=TIMESTAMP),
        ]
        provider.fetch_conditions_batch(requests)

        currents_calls = [c for c in reader.call_log if c["dataset_id"] == CURRENTS_DATASET]
        self.assertEqual(len(currents_calls), 1,
                         f"Expected 1 currents call, got {len(currents_calls)}")

    # -----------------------------------------------------------------------
    # 5. ONE waves request for N points (same timestamp)
    # -----------------------------------------------------------------------

    def test_05_one_waves_request_for_n_points(self):
        """5. All points sharing the same timestamp-hour use exactly 1 waves reader call."""
        reader, provider = self._make_reader_and_provider()
        requests = [
            ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP),
            ConditionRequest(lat=18.375, lon=70.875, timestamp=TIMESTAMP),
        ]
        provider.fetch_conditions_batch(requests)

        waves_calls = [c for c in reader.call_log if c["dataset_id"] == WAVES_DATASET]
        self.assertEqual(len(waves_calls), 1)

    # -----------------------------------------------------------------------
    # 6. Nearest-point extraction — closest row selected
    # -----------------------------------------------------------------------

    def test_06_nearest_point_extraction(self):
        """6. _extract_nearest_from_batch_df selects the closest row by L2 degree distance."""
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=lambda **kw: None)
        df = make_currents_df([
            {"latitude": 18.0, "longitude": 70.0, "uo": 1.0, "vo": 0.0},
            {"latitude": 18.5, "longitude": 70.5, "uo": 2.0, "vo": 0.0},
            {"latitude": 19.0, "longitude": 71.0, "uo": 3.0, "vo": 0.0},
        ])
        # Target (18.1, 70.1) is closest to row 0
        val = provider._extract_nearest_from_batch_df(df, "uo", CURRENTS_DATASET, 18.1, 70.1)
        self.assertAlmostEqual(val, 1.0, places=9)

        # Target (18.6, 70.6) is closest to row 1
        val2 = provider._extract_nearest_from_batch_df(df, "uo", CURRENTS_DATASET, 18.6, 70.6)
        self.assertAlmostEqual(val2, 2.0, places=9)

    # -----------------------------------------------------------------------
    # 7. Multiple coordinates — each gets correct value
    # -----------------------------------------------------------------------

    def test_07_multiple_coordinates_correct_values(self):
        """7. Each requested coordinate receives its correct nearest value."""
        reader, provider = self._make_reader_and_provider()
        requests = [
            ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP),
            ConditionRequest(lat=18.375, lon=70.875, timestamp=TIMESTAMP),
        ]
        results = provider.fetch_conditions_batch(requests)

        self.assertIn(requests[0], results)
        self.assertIn(requests[1], results)

        env_a = results[requests[0]]
        env_b = results[requests[1]]

        # Point A: uo=0.15, vo=0.08 -> convert to speed + direction
        from naudisha.data.copernicus_schema import convert_current_vectors_to_speed_and_direction
        expected_speed_a, expected_dir_a = convert_current_vectors_to_speed_and_direction(0.15, 0.08)
        self.assertAlmostEqual(env_a.current_speed, expected_speed_a, places=9)
        self.assertAlmostEqual(env_a.current_direction, expected_dir_a, places=6)
        self.assertAlmostEqual(env_a.wave_height, 2.1, places=6)
        self.assertAlmostEqual(env_a.wave_direction, 240.0, places=6)

        # Point B: uo=-0.05, vo=0.20
        expected_speed_b, expected_dir_b = convert_current_vectors_to_speed_and_direction(-0.05, 0.20)
        self.assertAlmostEqual(env_b.current_speed, expected_speed_b, places=9)
        self.assertAlmostEqual(env_b.wave_height, 1.8, places=6)

    # -----------------------------------------------------------------------
    # 8. Multiple timestamps — bucketed separately
    # -----------------------------------------------------------------------

    def test_08_multiple_timestamps_bucketed(self):
        """8. Requests with different timestamp-hours generate separate bucket queries."""
        reader = FakeBatchReader()
        reader.register(CURRENTS_DATASET, make_standard_currents_df())
        reader.register(WAVES_DATASET, make_standard_waves_df())
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        requests = [
            ConditionRequest(lat=18.125, lon=70.625, timestamp="2026-08-15T12:00:00Z"),
            ConditionRequest(lat=18.375, lon=70.875, timestamp="2026-08-15T18:00:00Z"),  # Different hour
        ]
        provider.fetch_conditions_batch(requests)

        # Each hour generates 1 currents + 1 waves call = 2 total buckets x 2 calls = 4
        currents_calls = [c for c in reader.call_log if c["dataset_id"] == CURRENTS_DATASET]
        self.assertEqual(len(currents_calls), 2)  # One per hour-bucket

    # -----------------------------------------------------------------------
    # 9. Missing current data
    # -----------------------------------------------------------------------

    def test_09_missing_current_data_raises_error(self):
        """9. Empty currents DataFrame raises CopernicusDataUnavailableError."""
        reader = FakeBatchReader()
        reader.register(CURRENTS_DATASET, pd.DataFrame(columns=["latitude", "longitude", "uo", "vo"]))
        reader.register(WAVES_DATASET, make_standard_waves_df())
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 10. Missing wave data
    # -----------------------------------------------------------------------

    def test_10_missing_wave_data_raises_error(self):
        """10. Empty waves DataFrame raises CopernicusDataUnavailableError."""
        reader = FakeBatchReader()
        reader.register(CURRENTS_DATASET, make_standard_currents_df())
        reader.register(WAVES_DATASET, pd.DataFrame(columns=["latitude", "longitude", "VHM0", "VMDR", "VTPK"]))
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 11. NaN current value
    # -----------------------------------------------------------------------

    def test_11_nan_current_value_raises_error(self):
        """11. NaN uo value raises CopernicusDataUnavailableError."""
        reader = FakeBatchReader()
        df_cur = make_currents_df([
            {"latitude": 18.125, "longitude": 70.625, "uo": float("nan"), "vo": float("nan")},
        ])
        reader.register(CURRENTS_DATASET, df_cur)
        reader.register(WAVES_DATASET, make_standard_waves_df())
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 12. NaN wave value
    # -----------------------------------------------------------------------

    def test_12_nan_wave_value_raises_error(self):
        """12. All-NaN VHM0 column raises CopernicusDataUnavailableError."""
        reader = FakeBatchReader()
        reader.register(CURRENTS_DATASET, make_standard_currents_df())
        df_wav = make_waves_df([
            {"latitude": 18.125, "longitude": 70.625, "VHM0": float("nan"), "VMDR": 240.0, "VTPK": 8.5},
        ])
        reader.register(WAVES_DATASET, df_wav)
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 13. Missing variable column in batch response
    # -----------------------------------------------------------------------

    def test_13_missing_variable_column_raises_error(self):
        """13. Missing 'uo' column in currents DataFrame raises CopernicusDataUnavailableError."""
        reader = FakeBatchReader()
        df_bad = pd.DataFrame([
            {"latitude": 18.125, "longitude": 70.625, "vo": 0.1}
            # 'uo' missing
        ])
        reader.register(CURRENTS_DATASET, df_bad)
        reader.register(WAVES_DATASET, make_standard_waves_df())
        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        with self.assertRaises(CopernicusDataUnavailableError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 14. Authentication failure
    # -----------------------------------------------------------------------

    def test_14_authentication_failure(self):
        """14. Reader raising credentials/unauthorized exception maps to CopernicusAuthenticationError."""
        def auth_failing_reader(**kwargs):
            raise Exception("Unauthorized: credentials invalid or missing")

        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=auth_failing_reader)

        with self.assertRaises(CopernicusAuthenticationError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 15. Network failure
    # -----------------------------------------------------------------------

    def test_15_network_failure(self):
        """15. Generic reader exception maps to CopernicusProviderError."""
        def network_failing_reader(**kwargs):
            raise RuntimeError("Connection timed out")

        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=network_failing_reader)

        with self.assertRaises(CopernicusProviderError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)
            ])

    # -----------------------------------------------------------------------
    # 16. Batch cache behavior
    # -----------------------------------------------------------------------

    def test_16_batch_cache_prevents_duplicate_reader_calls(self):
        """16. Second batch call for same coordinates uses cache — no additional reader calls."""
        reader, provider = self._make_reader_and_provider()
        provider.enable_cache = True  # Re-enable cache for this test

        requests = [ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)]
        provider.fetch_conditions_batch(requests)
        first_call_count = reader.call_count  # Should be 2 (1 currents + 1 waves)

        provider.fetch_conditions_batch(requests)
        second_call_count = reader.call_count

        self.assertEqual(first_call_count, 2)
        self.assertEqual(second_call_count, first_call_count,
                         "Second call should not trigger any reader calls (all cached)")

    # -----------------------------------------------------------------------
    # 17. Empty request list
    # -----------------------------------------------------------------------

    def test_17_empty_request_list_returns_empty_dict(self):
        """17. fetch_conditions_batch([]) returns an empty dict without any reader calls."""
        reader, provider = self._make_reader_and_provider()
        results = provider.fetch_conditions_batch([])
        self.assertEqual(results, {})
        self.assertEqual(reader.call_count, 0)

    # -----------------------------------------------------------------------
    # 18. Single-point batch — equivalence with fetch_conditions()
    # -----------------------------------------------------------------------

    def test_18_single_point_batch_matches_single_point_fetch(self):
        """18. Batch with 1 point produces the same result as fetch_conditions() for that point."""
        reader = FakeBatchReader()
        # Register same df for both methods (single-point uses point query, batch uses bbox)
        df_cur = make_currents_df([
            {"latitude": 18.125, "longitude": 70.625, "uo": 0.15, "vo": 0.08}
        ])
        df_wav = make_waves_df([
            {"latitude": 18.125, "longitude": 70.625, "VHM0": 2.1, "VMDR": 240.0, "VTPK": 8.5}
        ])
        reader.register(CURRENTS_DATASET, df_cur)
        reader.register(WAVES_DATASET, df_wav)

        provider = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)
        req = ConditionRequest(lat=18.125, lon=70.625, timestamp=TIMESTAMP)

        batch_result = provider.fetch_conditions_batch([req])[req]

        # Reload reader to get fresh fetch_conditions call
        reader2 = FakeBatchReader()
        reader2.register(CURRENTS_DATASET, df_cur)
        reader2.register(WAVES_DATASET, df_wav)
        provider2 = CopernicusMarineProvider(enable_cache=False, reader_fn=reader2)
        single_result = provider2.fetch_conditions(lat=18.125, lon=70.625, timestamp=TIMESTAMP)

        self.assertAlmostEqual(batch_result.current_speed, single_result.current_speed, places=9)
        self.assertAlmostEqual(batch_result.current_direction, single_result.current_direction, places=6)
        self.assertAlmostEqual(batch_result.wave_height, single_result.wave_height, places=9)
        self.assertAlmostEqual(batch_result.wave_direction, single_result.wave_direction, places=9)
        self.assertAlmostEqual(batch_result.wave_period, single_result.wave_period, places=9)

    # -----------------------------------------------------------------------
    # 19. Coordinate validation
    # -----------------------------------------------------------------------

    def test_19_coordinate_validation(self):
        """19. Out-of-range lat/lon in any request raises ValueError."""
        reader, provider = self._make_reader_and_provider()

        with self.assertRaises(ValueError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=95.0, lon=70.0, timestamp=TIMESTAMP)  # lat > 90
            ])

        with self.assertRaises(ValueError):
            provider.fetch_conditions_batch([
                ConditionRequest(lat=18.0, lon=185.0, timestamp=TIMESTAMP)  # lon > 180
            ])

    # -----------------------------------------------------------------------
    # 20. Regression/Equivalence: batch and per-point produce identical edge costs
    # -----------------------------------------------------------------------

    def test_20_batch_edge_costs_match_per_edge_costs(self):
        """
        20. REGRESSION/EQUIVALENCE: Grid populated via batch provider produces
        identical edge costs to grid populated via per-edge provider.

        This is the critical correctness gate: batching must not change routing results.
        Uses a composite-style wrapper to inject wind data (CMEMS returns wind=None).
        """
        from naudisha.data.weather_provider import BatchCapableProvider, ConditionRequest
        from typing import Sequence, Dict

        # Build comprehensive DataFrames covering all midpoints in 3x3 grid.
        # Use UNIFORM environmental values so that both the per-point path (which
        # takes iloc[0] without spatial selection) and the batch path (which uses
        # L2-nearest) resolve to the same values regardless of DataFrame row order.
        midpoints = [
            (18.25, 72.00), (18.00, 72.25), (18.25, 72.50), (18.50, 72.25),
            (18.75, 72.00), (18.50, 72.50), (18.75, 72.50), (18.00, 72.00),
            (18.50, 72.00), (18.00, 72.50), (18.75, 72.25), (18.25, 72.25),
        ]
        cur_rows = [
            {"latitude": lat, "longitude": lon, "uo": 0.15, "vo": 0.08}
            for lat, lon in midpoints
        ]
        wav_rows = [
            {"latitude": lat, "longitude": lon, "VHM0": 2.1, "VMDR": 240.0, "VTPK": 8.5}
            for lat, lon in midpoints
        ]
        df_cur = pd.DataFrame(cur_rows)
        df_wav = pd.DataFrame(wav_rows)

        # Wrapper that adds constant wind on top of CMEMS marine data
        class WindedBatchProvider(WeatherProvider, BatchCapableProvider):
            def __init__(self, marine: CopernicusMarineProvider):
                self._marine = marine

            def fetch_conditions(self, lat, lon, timestamp):
                marine_env = self._marine.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)
                return EnvironmentalData(
                    timestamp=marine_env.timestamp,
                    wind_speed=12.0, wind_direction=270.0,
                    wave_height=marine_env.wave_height,
                    wave_direction=marine_env.wave_direction,
                    wave_period=marine_env.wave_period,
                    current_speed=marine_env.current_speed,
                    current_direction=marine_env.current_direction,
                )

            def fetch_conditions_batch(self, requests):
                marine_results = self._marine.fetch_conditions_batch(requests)
                return {
                    req: EnvironmentalData(
                        timestamp=env.timestamp,
                        wind_speed=12.0, wind_direction=270.0,
                        wave_height=env.wave_height,
                        wave_direction=env.wave_direction,
                        wave_period=env.wave_period,
                        current_speed=env.current_speed,
                        current_direction=env.current_direction,
                    )
                    for req, env in marine_results.items()
                }

        # --- Batch provider ---
        batch_reader = FakeBatchReader()
        batch_reader.register("cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i", df_cur)
        batch_reader.register("cmems_mod_glo_wav_anfc_0.083deg_PT3H-i", df_wav)
        marine_batch = CopernicusMarineProvider(enable_cache=False, reader_fn=batch_reader)
        batch_provider = WindedBatchProvider(marine_batch)

        # --- Per-edge provider ---
        point_reader = FakeBatchReader()
        point_reader.register("cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i", df_cur)
        point_reader.register("cmems_mod_glo_wav_anfc_0.083deg_PT3H-i", df_wav)
        marine_per = CopernicusMarineProvider(enable_cache=False, reader_fn=point_reader)

        class PerEdgeWrapper(WeatherProvider):
            def __init__(self, delegate):
                self._delegate = delegate
            def fetch_conditions(self, lat, lon, timestamp):
                marine_env = self._delegate.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)
                return EnvironmentalData(
                    timestamp=marine_env.timestamp,
                    wind_speed=12.0, wind_direction=270.0,
                    wave_height=marine_env.wave_height, wave_direction=marine_env.wave_direction,
                    wave_period=marine_env.wave_period, current_speed=marine_env.current_speed,
                    current_direction=marine_env.current_direction,
                )

        ship = ShipProfile(
            ship_type="Test", length=200.0, beam=30.0, draft=9.0,
            cruising_speed=15.0, maximum_speed=20.0,
        )
        config = GridConfig(
            origin_lat=18.0, origin_lon=72.0, rows=3, cols=3,
            lat_spacing=0.5, lon_spacing=0.5,
        )
        timestamp = "2026-08-15T12:00:00Z"

        graph_batch = GeographicGridGraph(config=config, default_ship=ship)
        graph_batch.populate_environment(timestamp=timestamp, provider=batch_provider, ship=ship)

        graph_per_edge = GeographicGridGraph(config=config, default_ship=ship)
        graph_per_edge.populate_environment(
            timestamp=timestamp, provider=PerEdgeWrapper(marine_per), ship=ship,
        )

        # Verify batch path was used (BatchCapableProvider detected)
        self.assertIsInstance(batch_provider, BatchCapableProvider)
        self.assertNotIsInstance(PerEdgeWrapper(marine_per), BatchCapableProvider)

        # Compare all edge costs
        for (src, tgt) in graph_batch._edges:
            cost_batch = graph_batch.get_edge_cost(src, tgt)
            cost_per_edge = graph_per_edge.get_edge_cost(src, tgt)
            self.assertAlmostEqual(
                cost_batch, cost_per_edge, places=9,
                msg=f"Edge {src}->{tgt}: batch={cost_batch:.6f} != per_edge={cost_per_edge:.6f}"
            )


# ---------------------------------------------------------------------------
# Graph Integration Tests
# ---------------------------------------------------------------------------

class TestGraphBatchIntegration(unittest.TestCase):
    """
    Integration tests verifying that GeographicGridGraph correctly uses the batch
    path when given a BatchCapableProvider, and falls back for non-batch providers.
    """

    def _make_grid_components(self, rows=3, cols=3):
        config = GridConfig(
            origin_lat=18.0, origin_lon=72.0, rows=rows, cols=cols,
            lat_spacing=0.5, lon_spacing=0.5,
        )
        ship = ShipProfile(
            ship_type="Test Vessel", length=200.0, beam=30.0, draft=9.0,
            cruising_speed=15.0, maximum_speed=20.0,
        )
        return config, ship

    def _make_comprehensive_dfs(self, rows, cols):
        """Generate DataFrames that cover all edge midpoints for an NxN grid, with wind."""
        lat_min, lat_max = 17.5, 19.5
        lon_min, lon_max = 71.5, 73.5
        lats = [lat_min + i * 0.25 for i in range(int((lat_max - lat_min) / 0.25) + 1)]
        lons = [lon_min + j * 0.25 for j in range(int((lon_max - lon_min) / 0.25) + 1)]

        cur_rows = []
        wav_rows = []
        for lat in lats:
            for lon in lons:
                cur_rows.append({"latitude": lat, "longitude": lon, "uo": 0.1, "vo": 0.05})
                wav_rows.append({"latitude": lat, "longitude": lon, "VHM0": 1.5, "VMDR": 240.0, "VTPK": 7.0})

        return pd.DataFrame(cur_rows), pd.DataFrame(wav_rows)

    def _make_winded_batch_provider(self, reader: FakeBatchReader):
        """Creates a BatchCapableProvider that wraps CMEMS and injects constant wind data."""
        marine = CopernicusMarineProvider(enable_cache=False, reader_fn=reader)

        class WindedBatchProvider(WeatherProvider, BatchCapableProvider):
            def __init__(self, m):
                self._m = m
            def fetch_conditions(self, lat, lon, timestamp):
                env = self._m.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)
                return EnvironmentalData(
                    timestamp=env.timestamp, wind_speed=12.0, wind_direction=270.0,
                    wave_height=env.wave_height, wave_direction=env.wave_direction,
                    wave_period=env.wave_period, current_speed=env.current_speed,
                    current_direction=env.current_direction,
                )
            def fetch_conditions_batch(self, requests):
                marine_res = self._m.fetch_conditions_batch(requests)
                return {
                    req: EnvironmentalData(
                        timestamp=e.timestamp, wind_speed=12.0, wind_direction=270.0,
                        wave_height=e.wave_height, wave_direction=e.wave_direction,
                        wave_period=e.wave_period, current_speed=e.current_speed,
                        current_direction=e.current_direction,
                    )
                    for req, e in marine_res.items()
                }

        return WindedBatchProvider(marine), marine

    def test_21_batch_graph_uses_2_reader_calls_for_all_edges(self):
        """
        21. Graph with BatchCapableProvider + 3x3 grid (24 edges):
        batch reader called exactly 2 times (1 currents + 1 waves), not 24 times.
        """
        config, ship = self._make_grid_components(rows=3, cols=3)
        df_cur, df_wav = self._make_comprehensive_dfs(3, 3)

        reader = FakeBatchReader()
        reader.register("cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i", df_cur)
        reader.register("cmems_mod_glo_wav_anfc_0.083deg_PT3H-i", df_wav)

        provider, marine = self._make_winded_batch_provider(reader)
        self.assertIsInstance(provider, BatchCapableProvider)

        graph = GeographicGridGraph(config=config, default_ship=ship)
        graph.populate_environment(timestamp="2026-08-15T12:00:00Z", provider=provider, ship=ship)

        # The underlying marine reader should have been called exactly 2 times
        # (1 currents + 1 waves for the full bbox)
        self.assertEqual(reader.call_count, 2,
                         f"Expected 2 batch reader calls, got {reader.call_count}")

        # All edges should have finite cost after batch population
        finite_edges = sum(
            1 for cost in [graph.get_edge_cost(s, t) for s, t in graph._edges]
            if math.isfinite(cost)
        )
        self.assertEqual(finite_edges, 24, f"Expected 24 finite-cost edges, got {finite_edges}")

    def test_22_non_batch_provider_uses_per_edge_fallback(self):
        """
        22. Provider without BatchCapableProvider uses the per-edge fallback path.
        Reader called N times (once per edge), not 2.
        """
        config, ship = self._make_grid_components(rows=3, cols=3)

        call_count = [0]

        class NonBatchProvider(WeatherProvider):
            def fetch_conditions(self, lat, lon, timestamp):
                call_count[0] += 1
                return EnvironmentalData(
                    timestamp=str(timestamp),
                    wind_speed=10.0,
                    wind_direction=270.0,
                    wave_height=1.5,
                    wave_direction=250.0,
                    wave_period=7.0,
                    current_speed=0.5,
                    current_direction=90.0,
                )

        provider = NonBatchProvider()
        self.assertNotIsInstance(provider, BatchCapableProvider)

        graph = GeographicGridGraph(config=config, default_ship=ship)
        graph.populate_environment(timestamp="2026-08-15T12:00:00Z", provider=provider, ship=ship)

        # Should be called 24 times (once per navigable edge in 3x3 grid)
        self.assertEqual(call_count[0], 24,
                         f"Expected 24 per-edge provider calls, got {call_count[0]}")


if __name__ == "__main__":
    unittest.main()
