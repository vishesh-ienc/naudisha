# Current Prompt: Phase 8.2 — Live Environmental Route Planning

## Goal

Connect the existing NauDisha Backend API to the live environmental + routing engine via `RoutePlanningService` using the Phase 7.5 batch environmental pipeline (`BatchCapableProvider`).

```
USER / FRONTEND
       ↓
POST /api/routes/preview
       ↓
RoutePlanningService
       ↓
CompositeEnvironmentalProvider (BatchCapableProvider)
       ↓
CMEMS Bounding Box (Currents + Waves) + Open-Meteo Cell Dedup (Wind)
       ↓
EnvironmentalData
       ↓
GeographicGridGraph
       ↓
CostModel
       ↓
D* Lite Pathfinding
       ↓
Optimal Route Result
       ↓
Contract-compliant JSON Response (docs/API_CONTRACT.md)
```

---

## 1. Branch Strategy

- **Working Branch**: `feature/backend-api`
- Tracked on remote: `origin/feature/backend-api`
- `main` branch remains untouched.

---

## 2. Key Implementations in Phase 8.2

1. **`RoutePlanningService` Live Environmental Integration**:
   - Default provider configured to `CompositeEnvironmentalProvider` (combining Copernicus Marine physics/waves with Open-Meteo atmospheric wind).
   - Injected into `GeographicGridGraph` during dynamic corridor grid instantiation.
2. **Phase 7.5 Batch Pipeline Utilization**:
   - Automatically detects `isinstance(provider, BatchCapableProvider)`.
   - Populates all edge midpoints using CMEMS bounding box queries and deduplicated Open-Meteo requests in a single batch.
3. **Dynamic Corridor Grid Construction**:
   - `_build_bounding_grid(start_lat, start_lon, dest_lat, dest_lon)` dynamically bounds the departure and destination with protective margins and configurable resolution (`0.25°` ~ 15 NM).
   - Maps start and destination coordinates to distinct navigable grid nodes.
4. **Live Integration Demo (`examples/run_live_api_route_demo.py`)**:
   - Real-world route from Offshore Arabian Sea `(18.00°N, 71.00°E)` to Mumbai Approach `(19.00°N, 72.00°E)`.
   - Successfully executed with live data in **89.70 seconds** (including remote CMEMS batch download).
   - Output: 9 waypoints, **117.14 NM**, **6.48 hours** (~0.27 days), accumulated cost: **19.96**.

---

## 3. Core Invariant: Zero Touch to Routing Engine

- **D* Lite Algorithm** (`naudisha/routing/dstar_lite.py`): **0 lines changed**
- **GeographicGridGraph** (`naudisha/routing/graph.py`): **0 lines changed**
- **CostModel & Scorers** (`naudisha/cost/`): **0 lines changed**
- **Copernicus & Open-Meteo Mathematics** (`naudisha/data/`): **0 lines changed**

---

## 4. Test Suite: 141/141 Passing (3 New Tests)

Run command:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Coverage Added in `tests/test_api.py`:

| # | Test Case | Target Verification | Status |
|---|---|---|---|
| 17 | `test_17_service_uses_batch_capable_provider_pipeline` | Verifies `RoutePlanningService` calls `fetch_conditions_batch()` on batch-capable providers with all edge midpoints | ✅ PASS |
| 18 | `test_18_default_provider_is_composite_environmental_provider` | Verifies default `RoutePlanningService` initializes `CompositeEnvironmentalProvider` | ✅ PASS |
| 19 | `test_19_bounding_grid_covers_corridor_with_margin` | Verifies dynamic grid generator covers departure and destination with spatial margins | ✅ PASS |

**Previous test count**: 138  
**New test count**: 141 (3 new, 0 regressions)

---

## 5. Files Created & Modified

| File | Change |
|---|---|
| `naudisha/api/services.py` | Updated `RoutePlanningService` to default to `CompositeEnvironmentalProvider`, improved bounding grid & node mapping |
| `tests/test_api.py` | Added 3 new offline tests for batch capability, default provider, and corridor bounding margins |
| `examples/run_live_api_route_demo.py` | **NEW** — Live CMEMS + Open-Meteo API route preview demo with timing |
| `PROGRESS.md` | Documented Phase 8.2 milestone, batch usage, live demo metrics, and test progression |
| `current_prompt_implementation_walkthrough.md` | Updated current prompt walkthrough for Phase 8.2 |
