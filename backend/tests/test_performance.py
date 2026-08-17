"""
Unit and integration tests for Phase 15 Performance and Stage Optimizations.
Verifies batch wind extraction, cKDTree multi-variable extraction, midpoint dedup,
and asynchronous planning stage progress.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from naudisha.core.models import EnvironmentalData, ShipProfile, CostWeights
from naudisha.data.weather_provider import ConditionRequest
from naudisha.data.wind_provider import OpenMeteoWindProvider
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.routing.graph import GeographicGridGraph
from naudisha.api.planning import PlanningManager, PlanJob
from naudisha.api.services import RoutePlanningService


class TestPerformanceOptimizations(unittest.TestCase):
    """Tests Phase 15 performance mechanisms and behavioral fidelity."""

    def test_wind_provider_batch_parsing(self):
        ts = "2026-08-17T12:00:00Z"
        reqs = [
            ConditionRequest(lat=18.85, lon=72.45, timestamp=ts),
            ConditionRequest(lat=15.00, lon=73.00, timestamp=ts),
        ]

        fake_payload = [
            {
                "hourly": {
                    "time": ["2026-08-17T12:00"],
                    "wind_speed_10m": [14.2],
                    "wind_direction_10m": [220.0],
                },
                "hourly_units": {"wind_speed_10m": "kn"},
            },
            {
                "hourly": {
                    "time": ["2026-08-17T12:00"],
                    "wind_speed_10m": [18.5],
                    "wind_direction_10m": [245.0],
                },
                "hourly_units": {"wind_speed_10m": "kn"},
            },
        ]

        provider = OpenMeteoWindProvider(enable_cache=False, fetcher_fn=lambda url, timeout: fake_payload)
        res = provider.fetch_wind_batch(reqs)

        self.assertEqual(len(res), 2)
        self.assertAlmostEqual(res[reqs[0]][0], 14.2, places=2)
        self.assertAlmostEqual(res[reqs[0]][1], 220.0, places=2)
        self.assertAlmostEqual(res[reqs[1]][0], 18.5, places=2)
        self.assertAlmostEqual(res[reqs[1]][1], 245.0, places=2)

    def test_ckdtree_extraction_matches_ground_truth(self):
        provider = CopernicusMarineProvider(enable_cache=False)

        # Create a synthetic spatial grid dataframe
        lats = [18.0, 18.5, 19.0]
        lons = [72.0, 72.5, 73.0]
        rows = []
        for lat in lats:
            for lon in lons:
                rows.append({
                    "latitude": lat,
                    "longitude": lon,
                    "uo": 0.5 * (lat - 18.0) + 0.1,
                    "vo": -0.2 * (lon - 72.0) - 0.1,
                })
        df = pd.DataFrame(rows)

        target_coords = [(18.4, 72.4), (18.9, 72.9), (18.1, 72.1)]

        # 1. Multi vectorized cKDTree extraction
        extracted_multi = provider._extract_nearest_multi_from_batch_df(
            df, ["uo", "vo"], "mock_dataset", target_coords
        )

        # 2. Ground truth single extraction
        for i, (t_lat, t_lon) in enumerate(target_coords):
            expected_uo = provider._extract_nearest_from_batch_df(df, "uo", "mock_dataset", t_lat, t_lon)
            expected_vo = provider._extract_nearest_from_batch_df(df, "vo", "mock_dataset", t_lat, t_lon)

            self.assertAlmostEqual(extracted_multi["uo"][i], expected_uo, places=4)
            self.assertAlmostEqual(extracted_multi["vo"][i], expected_vo, places=4)

    def test_midpoint_deduplication_in_graph(self):
        # Create a small 3x3 grid using GridConfig
        from naudisha.routing.graph import GridConfig
        cfg = GridConfig(
            origin_lat=18.0,
            origin_lon=72.0,
            rows=3,
            cols=3,
            lat_spacing=0.5,
            lon_spacing=0.5,
        )
        graph = GeographicGridGraph(config=cfg)

        mock_batch_provider = MagicMock(spec=CompositeEnvironmentalProvider)
        mock_batch_provider.fetch_conditions_batch = MagicMock(
            side_effect=lambda reqs: {
                req: EnvironmentalData(
                    timestamp="2026-08-17T12:00:00Z",
                    wind_speed=15.0,
                    wind_direction=90.0,
                    wave_height=1.5,
                    wave_direction=90.0,
                    wave_period=7.0,
                    current_speed=0.5,
                    current_direction=45.0,
                )
                for req in reqs
            }
        )

        # Graph has 9 nodes, 24 directed edges (12 bidirectional connections)
        ship = ShipProfile(
            ship_type="Cargo",
            length=200.0,
            beam=32.0,
            draft=10.0,
            cruising_speed=14.0,
            maximum_speed=20.0,
        )
        graph.populate_environment(
            timestamp="2026-08-17T12:00:00Z",
            provider=mock_batch_provider,
            ship=ship,
            weights=CostWeights(),
        )

        # Ensure fetch_conditions_batch was called with deduplicated requests
        called_reqs = mock_batch_provider.fetch_conditions_batch.call_args[0][0]
        # In a 3x3 4-connected grid with 24 directed edges, there are exactly 12 unique midpoints
        self.assertEqual(len(called_reqs), 12)

        # All 24 edges must have valid env_data populated
        for edge in graph._edges.values():
            if edge.is_navigable:
                self.assertIsNotNone(edge.env_data)
                self.assertAlmostEqual(edge.env_data.wind_speed, 15.0)

    def test_planning_manager_stage_progress(self):
        from naudisha.data.weather_provider import MockWeatherProvider
        pm = PlanningManager()
        # Service with Mock provider for instant deterministic execution
        service = RoutePlanningService(environment_provider=MockWeatherProvider())
        pm.set_route_service(service)

        sig = ("TEST_STAGE", 18.85, 72.45, 18.00, 73.00, "2026-08-17T12", "balanced")
        job = pm.submit(
            sig,
            imo_number="TEST_STAGE",
            start_lat=18.85,
            start_lon=72.45,
            dest_lat=18.00,
            dest_lon=73.00,
            timestamp="2026-08-17T12:00:00Z",
            optimization_objective="balanced",
        )

        # Wait for worker thread to complete
        import time
        start_t = time.monotonic()
        while job.status == "planning" and time.monotonic() - start_t < 10.0:
            time.sleep(0.05)

        self.assertEqual(job.status, "ready")
        self.assertEqual(job.stage, "ready")
        self.assertEqual(job.progress_percent, 100.0)
        self.assertIsNotNone(job.result)


if __name__ == "__main__":
    unittest.main()
