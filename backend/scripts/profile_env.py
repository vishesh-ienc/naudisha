"""
Micro-profiler for Environmental Providers.
Measures Copernicus Marine currents, Copernicus Marine waves, and Open-Meteo wind.
"""

import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.weather_provider import ConditionRequest
from datetime import datetime, timezone

def profile_env_provider():
    provider = CompositeEnvironmentalProvider()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Sample a 5x5 grid midpoint set (~80 requests, ~40 unique midpoints)
    lats = [18.85 - i * 0.5 for i in range(5)]
    lons = [72.45 + j * 0.5 for j in range(5)]
    
    requests = []
    for lat in lats:
        for lon in lons:
            requests.append(ConditionRequest(lat=lat, lon=lon, timestamp=timestamp))

    print(f"Profiling Environmental Fetch for {len(requests)} ConditionRequests...")

    # 1. Measure CMEMS
    t0 = time.perf_counter()
    marine_res = provider.marine_provider.fetch_conditions_batch(requests)
    t_cmems = time.perf_counter() - t0
    print(f"  Copernicus Marine Batch (Currents + Waves): {t_cmems * 1000:.1f}ms ({t_cmems:.2f}s)")

    # 2. Measure Open-Meteo
    t0 = time.perf_counter()
    # Unique requests
    seen = set()
    unique_reqs = []
    for req in requests:
        cell_key = (round(req.lat, 2), round(req.lon, 2))
        if cell_key not in seen:
            seen.add(cell_key)
            unique_reqs.append(req)
    
    print(f"  Open-Meteo unique cells: {len(unique_reqs)}")
    for r in unique_reqs:
        provider.wind_provider.fetch_wind(lat=r.lat, lon=r.lon, timestamp=r.timestamp)
    t_wind = time.perf_counter() - t0
    print(f"  Open-Meteo Wind Total: {t_wind * 1000:.1f}ms ({t_wind:.2f}s)")

    # 3. Measure Full Batch
    t0 = time.perf_counter()
    full_res = provider.fetch_conditions_batch(requests)
    t_full = time.perf_counter() - t0
    print(f"  Full Composite Batch: {t_full * 1000:.1f}ms ({t_full:.2f}s)")

if __name__ == "__main__":
    profile_env_provider()
