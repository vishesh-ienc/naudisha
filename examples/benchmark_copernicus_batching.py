"""
NauDisha — Copernicus Marine Batch vs Sequential Performance Benchmark
======================================================================
Deterministic benchmark comparing:
    OLD:  N edges × 2 sequential reader calls  (1 currents + 1 waves per edge)
    NEW:  1 currents + 1 waves bounding-box request (batch)

All measurements use injected fake readers — no live CMEMS calls.
Results include: request counts, elapsed time, and result equivalence assertion.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List

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
from naudisha.data.copernicus_provider import CopernicusMarineProvider
from naudisha.routing.graph import (
    GridConfig,
    GeographicGridGraph,
)


# ---------------------------------------------------------------------------
# Fake readers
# ---------------------------------------------------------------------------

class CountingReader:
    """Fake copernicusmarine.read_dataframe that counts calls and returns pre-built DataFrames."""

    def __init__(self, df_currents: pd.DataFrame, df_waves: pd.DataFrame):
        self._responses = {
            "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i": df_currents,
            "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i": df_waves,
        }
        self.call_count = 0
        self.call_log: List[Dict] = []

    def __call__(self, **kwargs) -> pd.DataFrame:
        self.call_count += 1
        self.call_log.append(kwargs)
        dataset_id = kwargs.get("dataset_id", "")
        return self._responses.get(dataset_id, pd.DataFrame())


class WindedBatchProvider(WeatherProvider, BatchCapableProvider):
    """Wrapper adding constant wind data to CMEMS batch provider for CostModel compatibility."""

    def __init__(self, marine: CopernicusMarineProvider):
        self._marine = marine

    def fetch_conditions(self, lat, lon, timestamp):
        env = self._marine.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)
        return EnvironmentalData(
            timestamp=env.timestamp, wind_speed=12.0, wind_direction=270.0,
            wave_height=env.wave_height, wave_direction=env.wave_direction,
            wave_period=env.wave_period, current_speed=env.current_speed,
            current_direction=env.current_direction,
        )

    def fetch_conditions_batch(self, requests):
        marine_results = self._marine.fetch_conditions_batch(requests)
        return {
            req: EnvironmentalData(
                timestamp=env.timestamp, wind_speed=12.0, wind_direction=270.0,
                wave_height=env.wave_height, wave_direction=env.wave_direction,
                wave_period=env.wave_period, current_speed=env.current_speed,
                current_direction=env.current_direction,
            )
            for req, env in marine_results.items()
        }


class PerEdgeWrapper(WeatherProvider):
    """Non-batch wrapper that forces per-edge fetching path in the graph."""

    def __init__(self, marine: CopernicusMarineProvider):
        self._marine = marine

    def fetch_conditions(self, lat, lon, timestamp):
        env = self._marine.fetch_conditions(lat=lat, lon=lon, timestamp=timestamp)
        return EnvironmentalData(
            timestamp=env.timestamp, wind_speed=12.0, wind_direction=270.0,
            wave_height=env.wave_height, wave_direction=env.wave_direction,
            wave_period=env.wave_period, current_speed=env.current_speed,
            current_direction=env.current_direction,
        )


# ---------------------------------------------------------------------------
# DataFrame factory
# ---------------------------------------------------------------------------

def build_test_dataframes(grid_config: GridConfig):
    """Build dense fake DataFrames covering all possible edge midpoints."""
    lat_min = grid_config.origin_lat - 0.5
    lat_max = grid_config.origin_lat + (grid_config.rows + 1) * grid_config.lat_spacing
    lon_min = grid_config.origin_lon - 0.5
    lon_max = grid_config.origin_lon + (grid_config.cols + 1) * grid_config.lon_spacing

    lats = [lat_min + i * 0.083 for i in range(int((lat_max - lat_min) / 0.083) + 1)]
    lons = [lon_min + j * 0.083 for j in range(int((lon_max - lon_min) / 0.083) + 1)]

    cur_rows = []
    wav_rows = []
    for lat in lats:
        for lon in lons:
            cur_rows.append({"latitude": lat, "longitude": lon, "uo": 0.15, "vo": 0.08})
            wav_rows.append({"latitude": lat, "longitude": lon, "VHM0": 2.1, "VMDR": 240.0, "VTPK": 8.5})

    return pd.DataFrame(cur_rows), pd.DataFrame(wav_rows)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def run_benchmark():
    print("=" * 72)
    print("   NauDisha — Copernicus Marine Batch vs Sequential Benchmark")
    print("   (Deterministic — Injected Fake Readers — No Network Access)")
    print("=" * 72)

    ship = ShipProfile(
        ship_type="Benchmark Vessel", length=200.0, beam=30.0, draft=9.0,
        cruising_speed=15.0, maximum_speed=20.0,
    )
    timestamp = "2026-08-15T12:00:00Z"

    for grid_size in [(3, 3), (5, 5), (10, 10)]:
        rows, cols = grid_size
        config = GridConfig(
            origin_lat=18.0, origin_lon=72.0, rows=rows, cols=cols,
            lat_spacing=0.25, lon_spacing=0.25,
        )

        n_nodes = rows * cols
        n_edges = 2 * rows * (cols - 1) + 2 * (rows - 1) * cols  # Horizontal + vertical bidirectional

        df_cur, df_wav = build_test_dataframes(config)

        print(f"\n{'─' * 72}")
        print(f"  Grid: {rows}×{cols} ({n_nodes} nodes, {n_edges} directed edges)")
        print(f"{'─' * 72}")

        # --- Sequential (per-edge) ---
        seq_reader = CountingReader(df_cur, df_wav)
        seq_marine = CopernicusMarineProvider(enable_cache=False, reader_fn=seq_reader)
        seq_provider = PerEdgeWrapper(seq_marine)

        graph_seq = GeographicGridGraph(config=config, default_ship=ship)

        t0 = time.perf_counter()
        graph_seq.populate_environment(timestamp=timestamp, provider=seq_provider, ship=ship)
        t_seq = time.perf_counter() - t0

        # --- Batch ---
        batch_reader = CountingReader(df_cur, df_wav)
        batch_marine = CopernicusMarineProvider(enable_cache=False, reader_fn=batch_reader)
        batch_provider = WindedBatchProvider(batch_marine)

        graph_batch = GeographicGridGraph(config=config, default_ship=ship)

        t0 = time.perf_counter()
        graph_batch.populate_environment(timestamp=timestamp, provider=batch_provider, ship=ship)
        t_batch = time.perf_counter() - t0

        # --- Results ---
        print(f"\n  Sequential (OLD):")
        print(f"    Reader calls:       {seq_reader.call_count}")
        print(f"    Elapsed:            {t_seq * 1000:.1f} ms")

        print(f"\n  Batch (NEW):")
        print(f"    Reader calls:       {batch_reader.call_count}")
        print(f"    Elapsed:            {t_batch * 1000:.1f} ms")

        if t_seq > 0:
            speedup = t_seq / t_batch if t_batch > 0 else float("inf")
            print(f"\n  Speedup:              {speedup:.1f}x")
        print(f"  Request reduction:    {seq_reader.call_count} → {batch_reader.call_count}")

        # --- Equivalence check ---
        all_match = True
        for (src, tgt) in graph_seq._edges:
            c_seq = graph_seq.get_edge_cost(src, tgt)
            c_batch = graph_batch.get_edge_cost(src, tgt)
            if abs(c_seq - c_batch) > 1e-9:
                all_match = False
                print(f"  ⚠ MISMATCH: {src}->{tgt}: seq={c_seq:.6f} batch={c_batch:.6f}")
                break

        if all_match:
            print(f"\n  ✅ EQUIVALENCE VERIFIED: All {n_edges} edge costs match (tolerance: 1e-9)")
        else:
            print(f"\n  ❌ EQUIVALENCE FAILED")

    print(f"\n{'=' * 72}")
    print("   Benchmark complete.")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    run_benchmark()
