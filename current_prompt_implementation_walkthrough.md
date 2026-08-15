# Current Prompt: Phase 7.5 — Batch CMEMS Environmental Sampling

## Goal


Fix the environmental data acquisition bottleneck.

```
BEFORE:  80 edges × 2 CMEMS calls = 160 sequential HTTP requests → ~8-10 minutes
AFTER:   80 edges → bounding box → 1 currents + 1 waves = 2 requests → ~15-30 seconds
```

---

## New Abstractions

### `ConditionRequest` (frozen dataclass in `weather_provider.py`)

```python
@dataclass(frozen=True)
class ConditionRequest:
    lat: float
    lon: float
    timestamp: Union[datetime, str]
```

Hashable, usable as dict key. This is the element type for batch operations.

### `BatchCapableProvider` (separate ABC in `weather_provider.py`)

```python
class BatchCapableProvider(ABC):
    @abstractmethod
    def fetch_conditions_batch(
        self, requests: Sequence[ConditionRequest]
    ) -> Dict[ConditionRequest, EnvironmentalData]: ...
```

**Why a separate ABC?** Existing `WeatherProvider` is NOT modified. No breaking changes.
The graph uses `isinstance(provider, BatchCapableProvider)` for capability detection.

---

## Provider Changes

### `CopernicusMarineProvider` — now inherits `WeatherProvider + BatchCapableProvider`

New methods:
- `_execute_bbox_subset_query()` — takes explicit lat/lon/time ranges (not point + delta)
- `_extract_nearest_from_batch_df()` — L2 degree-space nearest-row selection
- `fetch_conditions_batch()` — groups by hour-bucket, one bbox query per bucket

**Existing `fetch_conditions()` is unchanged** — still uses the per-point path.

### `CompositeEnvironmentalProvider` — now inherits `WeatherProvider + BatchCapableProvider`

`fetch_conditions_batch()`:
1. Delegates CMEMS to `CopernicusMarineProvider.fetch_conditions_batch()` (1+1 requests)
2. Deduplicates Open-Meteo by `round(lat,2), round(lon,2)` cell key
3. Fetches unique cells (4-8 for a 5×5 grid spanning ~1°×1°)
4. Assembles combined `EnvironmentalData` per request

### `OpenMeteoWindProvider` — **unchanged**

Wind deduplication is handled in `CompositeEnvironmentalProvider` by pre-populating
the existing cache. No modifications to the wind provider itself.

---

## Graph Changes

### `populate_environment()` — batch detection added

```python
if isinstance(active_provider, BatchCapableProvider):
    requests = [ConditionRequest(lat, lon, timestamp) for each navigable edge midpoint]
    batch_results = active_provider.fetch_conditions_batch(requests)
    # assign to edges + recalculate costs
else:
    # existing per-edge loop (unchanged)
```

### `refresh_edges()` — batch detection added

Same pattern: `len(edges) > 1 and isinstance(provider, BatchCapableProvider)` → batch path.
Single-edge refresh still uses per-edge fallback.

**D* Lite, CostModel, edge cost mathematics: ZERO changes.**

---

## Test Suite: 122/122 Pass (22 New)

| # | Test | Key Assertion |
|---|---|---|
| 1 | ConditionRequest hashable | `d = {req: "v"}; d[req] == "v"` |
| 2 | Bounding box | `lat_min = min(lats) - 0.1`, etc. |
| 3 | Temporal range | `start = bucket_dt - 3h`, `end = bucket_dt + 3h` |
| 4 | 1 currents call for N points | `len(currents_calls) == 1` |
| 5 | 1 waves call for N points | `len(waves_calls) == 1` |
| 6 | Nearest-point extraction | L2 distance selects closest row |
| 7 | Multiple coordinates correct | Each gets its own nearest |
| 8 | Multiple timestamps bucketed | 2 hours → 2 currents calls |
| 9-12 | Missing/NaN data errors | `CopernicusDataUnavailableError` |
| 13 | Missing column | `CopernicusDataUnavailableError` |
| 14 | Auth failure | `CopernicusAuthenticationError` |
| 15 | Network failure | `CopernicusProviderError` |
| 16 | Cache prevents re-fetch | `second_call_count == first_call_count` |
| 17 | Empty list → empty dict | No reader calls |
| 18 | Single-point equivalence | `batch == fetch_conditions()` within 1e-9 |
| 19 | Coordinate validation | `ValueError` for lat > 90 |
| **20** | **Regression/equivalence** | All edge costs match within 1e-9 |
| **21** | **Graph batch: 2 calls for 24 edges** | `reader.call_count == 2` |
| 22 | Non-batch fallback | `call_count == 24` per-edge calls |

---

## Benchmark Results (Deterministic)

| Grid | Edges | Old Requests | New Requests | Reduction | Equivalence |
|---|---|---|---|---|---|
| 3×3 | 24 | 48 | 2 | 24× | ✅ |
| 5×5 | 80 | 160 | 2 | 80× | ✅ |
| 10×10 | 360 | 720 | 2 | 360× | ✅ |

---

## Files Changed

| File | Change |
|---|---|
| `naudisha/data/weather_provider.py` | Added `ConditionRequest`, `BatchCapableProvider` |
| `naudisha/data/copernicus_provider.py` | Added `BatchCapableProvider` inheritance, `_execute_bbox_subset_query`, `_extract_nearest_from_batch_df`, `fetch_conditions_batch` |
| `naudisha/data/composite_provider.py` | Added `BatchCapableProvider` inheritance, `fetch_conditions_batch` with Open-Meteo dedup |
| `naudisha/routing/graph.py` | Batch detection in `populate_environment()` and `refresh_edges()` |
| `naudisha/data/__init__.py` | Exported `ConditionRequest`, `BatchCapableProvider` |
| `naudisha/__init__.py` | Exported `ConditionRequest`, `BatchCapableProvider` |
| `tests/test_copernicus_batch_provider.py` | NEW — 22 offline tests |
| `examples/benchmark_copernicus_batching.py` | NEW — deterministic benchmark |
| `examples/run_live_batch_grid_demo.py` | NEW — live 5×5 batch demo |
| `PROGRESS.md` | Phase 7.5 section added |

**Previous test count**: 100
**New test count**: 122
**Regressions**: 0
