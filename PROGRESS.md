# NauDisha Project Progress Log

This document tracks the technical evolution, architectural milestones, design decisions, and future roadmap for **NauDisha — Dynamic & Optimal Ship Routing System** (SIH Project).

---

## 🗺 System Architecture Flow

The system is designed as a layered, modular maritime routing pipeline:

```
[ Dynamic Marine / Weather Providers ]  (NOAA / Copernicus / Mock)
                    │
                    ▼
[ Environmental & Vessel Data Contracts ]  (ShipProfile, EnvironmentalData, SegmentData)
                    │
                    ▼
       [ Derived Nautical Engine ]         (Haversine Distance, Bearing, Relative Vectors, SOG)
                    │
                    ▼
        [ Modular Cost Model ]             (Time, Fuel, Wind, Wave, Current, Safety [0, 1])
                    │
                    ▼
    [ Geographic Grid & Graph Layer ]      (GeographicGridGraph, 4-Direction Edges, O(1) Updates)
                    │
                    ▼  (Upcoming Phase 3)
     [ D* Lite Dynamic Pathfinding ]       (Incremental Heuristic Graph Replanning)
                    │
                    ▼  (Upcoming Phase 4)
      [ API & Visualization Engine ]       (Interactive Web Route Dashboard)
```

---

## 📌 Milestones & Progress Log

### Phase 1: Cost Model & Data Contracts Foundation ✅
**Status**: Completed  
**Commit**: `cdd8049`

- **Domain Data Models**:
  - Implemented immutable, validated dataclasses: `ShipProfile`, `EnvironmentalData`, `SegmentData`, `CostWeights`, `ScoringConfig`, and `SegmentEvaluation`.
- **Derived Nautical & Hydrodynamic Calculations**:
  - Mathematical implementation of spherical Haversine distance in NM and km.
  - Great-circle forward initial bearing $[0^\circ, 360^\circ)$.
  - Minimal relative angular difference $[0^\circ, 180^\circ]$ for wind, waves, and ocean currents.
  - Along-track current vector decomposition ($+ = \text{assisting}, - = \text{opposing}$).
  - Effective speed over ground (SOG) and travel time with safety clamping.
- **Six Modular Component Scorers**:
  - Implemented standard $[0.0, 1.0]$ normalized scoring convention ($0.0 = \text{optimal}, 1.0 = \text{worst}$).
  - Modular scorers: `time_score`, `fuel_score`, `wind_score`, `wave_score`, `current_score`, `safety_score`.
- **Cost Model Engine**:
  - Weighted multi-objective optimization with dynamic constraint enforcement.
  - Non-navigable segments return `math.inf`.
- **Verification**:
  - 23 unit tests passing in `tests/test_calculations.py`, `tests/test_normalization.py`, `tests/test_scorers.py`, and `tests/test_cost_model.py`.
  - Created runnable demonstration `examples/run_segment_cost.py`.

---

### Phase 2: Geographic Grid & Routing Environment Layer ✅
**Status**: Completed

- **Spatial Grid Abstraction**:
  - Created `GridConfig`, `GridNode`, `GridEdge`, and `GeographicGridGraph` in [`naudisha/routing/graph.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/routing/graph.py).
  - Configurable origin coordinates, grid dimensions ($rows \times cols$), and latitude/longitude resolution.
  - 4-direction planar movement (North, South, East, West).
- **Directed Graph Semantics**:
  - Directed edges represent directional environmental vector fields (e.g. heading North against a North wind has a different cost than heading South with a North wind).
- **CostModel Integration**:
  - Directly binds `CostModel` to compute edge traversal costs across all active segments.
- **$O(1)$ Dynamic Incremental Updates**:
  - `update_edge_environment()` updates individual segment weather forecasts and recalculates costs immediately without rebuilding the graph.
  - `set_node_navigability()` dynamically enables/disables waypoints (islands, shallows, hazards) and sets incident edge costs to `math.inf`.
- **D* Lite Query Interface Ready**:
  - Implemented `get_successors()`, `get_predecessors()`, `get_neighbors()`, `get_edge_cost()`, `is_node_navigable()`, and `is_edge_navigable()`.
- **Verification**:
  - 8 new unit tests added in `tests/test_graph.py` (Total 31 unit tests passing).
  - Created interactive demo `examples/run_grid_environment_demo.py`.

---

### Phase 3: D* Lite Dynamic Pathfinding Engine & Mathematical Audit ✅
**Status**: Completed & Mathematically Audited

- **Core Algorithm Implementation**:
  - Implemented the full incremental heuristic search algorithm by Koenig & Likhachev in [`naudisha/routing/dstar_lite.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/routing/dstar_lite.py).
  - Priority queue with lexicographic keys:
    $$k(u) = [\min(g(u), rhs(u)) + h(s_{\text{start}}, u) + k_m, \min(g(u), rhs(u))]$$
  - One-step lookahead $rhs(u)$ and cost-to-goal $g(u)$ tracking with lazy-deletion min-heap.
  - Moving start position support with accumulated heuristic modifier $k_m = k_m + h(s_{\text{last}}, s_{\text{start}})$.
  - Backward search from goal to start for rapid incremental path repair.
- **Heuristic Admissibility Audit & Resolution**:
  - **Problem**: Raw geographic distance in nautical miles (~30 NM per grid cell) has a different physical dimension than the dimensionless normalized $[0, \sum w_i]$ cost index ($\approx 1.5 - 3.5$ cost units per cell). An unscaled geographic heuristic would severely overestimate true cost ($30.0 > 1.8$), violating the fundamental admissibility requirement ($h(u, v) \le c^*(u, v)$) and destroying optimality guarantees.
  - **Resolution**: Set `heuristic_scale = 0.0` as the default baseline. This yields an unconditionally admissible ($0 \le c^*(u, v)$) and monotonic ($0 \le 0 + c(u, v)$) heuristic for all non-negative cost models, guaranteeing mathematical optimality. Optional `heuristic_scale` is configurable when a proven non-zero minimum cost per NM lower bound is supplied.
- **Dynamic Incremental Replanning**:
  - `update_edge(u, v)` updates only vertex $u$'s $rhs(u)$ value in $O(1)$ time when marine forecasts change.
  - `update_edges([(u, v), ...])` supports batch regional forecast updates.
  - `update_node(u)` updates vertex $u$ and its incoming predecessors/outgoing successors when obstacle/navigability flags change.
  - `replan()` incrementally repairs the shortest path tree without running $A^*$/Dijkstra from scratch or rebuilding the graph.
- **Independent Oracle Verification (51/51 Tests Passing)**:
  - Built an independent reference Dijkstra solver in `tests/test_dstar_lite_correctness.py` as a test oracle.
  - Rigorously tested initial optimality, dynamic cost increases (storms), cost decreases (shortcuts), simultaneous multiple edge changes, obstacle transitions, moving start, and unreachable goals against Dijkstra.
  - Verified 100% mathematical cost equality ($D^* \text{ Lite Cost} == \text{Dijkstra Oracle Cost}$).
  - Created interactive demonstration `examples/run_dstar_lite_demo.py` showcasing dynamic storm intercept, optimal detour replanning, and oracle cross-verification.

---

### Phase 4: Copernicus Marine Service Provider & Oceanographic Ingestion ✅
**Status**: Completed (Ocean Currents & Waves Live Provider Active)

- **Architecture Strategy & Flow**:
  $$\text{Copernicus Marine (Physics \& Waves)} \longrightarrow \text{EnvironmentalData} \longrightarrow \text{CostModel} \longrightarrow \text{GeographicGridGraph} \longrightarrow D^* \text{ Lite}$$
  - **Ocean Currents & Waves**: Sourced from Copernicus Marine Service (`cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i` and `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`).
  - **Wind Data**: Explicitly set to `None` in `EnvironmentalData` pending integration of a dedicated atmospheric weather provider in a future step.
  - **Decoupled Provider Abstraction**: `CopernicusMarineProvider` implements `WeatherProvider` without exposing Copernicus internal mechanics to `CostModel` or $D^*$ Lite.
- **Provider Capabilities**:
  - `fetch_conditions(lat, lon, timestamp)` fetches targeted spatial/temporal point subsets via `copernicusmarine.read_dataframe`.
  - In-memory cache `(round(lat, 2), round(lon, 2), timestamp_hour)` prevents redundant API queries during graph edge updates.
  - Mathematical vector conversions for ocean currents:
    $$v_{\text{knots}} = \sqrt{u_o^2 + v_o^2} \times 1.9438444924$$
    $$\theta_{\text{flow}} = \left(90^\circ - \text{atan2}(v_o, u_o) \cdot \frac{180}{\pi} + 360^\circ\right) \pmod{360^\circ}$$
  - Full exception hierarchy: `CopernicusProviderError`, `CopernicusAuthenticationError`, `CopernicusDataUnavailableError`.
  - Non-interactive pre-flight credential checks prevent automated hanging on missing local credentials.
- **Verification & Offline Test Suite (64/64 Tests Passing)**:
  - Added 7 offline unit tests in [`tests/test_copernicus_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/tests/test_copernicus_provider.py) testing query construction, conversion, missing values, NaN handling, cache hits, and authentication error translation using dependency injection.
  - Added live integration sample in [`examples/fetch_copernicus_sample.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/fetch_copernicus_sample.py).
  - Resolved depth dimension coordinate query bounds (`depth_level = 0.5m`) ensuring clean execution without coordinate subset warnings.
- **Live Integration Verification (Arabian Sea / Indian Ocean: 18.50°N, 72.00°E)**:
  - **Status**: Live CMEMS Fetch Verified Successfully ✅
  - **Retrieved Real Parameters**:
    - Ocean Current Speed: `0.36 knots`
    - Ocean Current Direction: `126.6°` (Flow heading towards SE)
    - Significant Wave Height ($H_s$): `2.46 meters`
    - Mean Wave Direction: `249.8°` (From WSW)
    - Peak Wave Period ($T_p$): `9.8 seconds`
    - Wind: `None` (Pending complementary atmospheric provider)

---

### Phase 5: Atmospheric Wind Provider & Unified Environmental Data Fusion ✅
**Status**: Completed (Open-Meteo Wind Provider & Composite Fusion Active)

- **Architecture Strategy & Data Flow**:
  $$\begin{aligned}
  \text{Copernicus Marine (Physics \& Waves)} &\longrightarrow \text{Currents } (u_o, v_o) + \text{Waves } (H_s, \text{dir}, T_p) \searrow \\
  \text{Open-Meteo Forecast (Atmosphere)} &\longrightarrow \text{Wind Vectors } (\text{speed}, \text{direction}) \longrightarrow \text{EnvironmentalData} \longrightarrow \text{CostModel} \longrightarrow D^* \text{ Lite}
  \end{aligned}$$
  - **Why Open-Meteo was added**: Copernicus Marine is the premier hydrodynamic authority but specializes in ocean physics. Open-Meteo provides a free, open, global atmospheric forecast API for 10-meter surface wind vectors (`wind_speed_10m`, `wind_direction_10m`) without requiring API keys.
  - **Copernicus Remains Primary**: Copernicus Marine remains the primary source for all ocean current vectors and spectral wave parameters.
- **Provider Implementation (`OpenMeteoWindProvider`)**:
  - Implements `WeatherProvider.fetch_conditions(lat, lon, timestamp)` in [`naudisha/data/wind_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/wind_provider.py).
  - API endpoint: `https://api.open-meteo.com/v1/forecast` requesting `wind_speed_10m` and `wind_direction_10m`.
  - Automatic nearest hourly time index matching.
  - Native unit conversion into knots ($1\text{ km/h} = 0.539957\text{ kn}$, $1\text{ m/s} = 1.943844\text{ kn}$) and degrees $[0, 360)$.
  - In-memory cache `(round(lat, 2), round(lon, 2), timestamp_hour)` prevents redundant HTTP requests.
  - Robust exception hierarchy: `WindProviderError`, `WindNetworkError`, `WindDataUnavailableError`, `WindResponseMalformedError`.
- **Unified Composite Provider (`CompositeEnvironmentalProvider`)**:
  - Implemented in [`naudisha/data/composite_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/composite_provider.py).
  - Fuses Copernicus hydrodynamic currents and spectral waves with Open-Meteo atmospheric wind into a single, fully populated `EnvironmentalData` model.
- **Verification & Testing (72/72 Unit Tests Passing)**:
  - Added 8 offline unit tests in [`tests/test_wind_provider.py`](file:///c:/Users/VISHESH/Desktop/naudisha/tests/test_wind_provider.py) covering JSON parsing, unit conversions, timestamp matching, cache hits, malformed responses, network failures, and coordinate bounds.
  - Added live integration example [`examples/fetch_wind_sample.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/fetch_wind_sample.py).
  - Added full multi-source fusion example [`examples/fetch_combined_environmental_sample.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/fetch_combined_environmental_sample.py) demonstrating real-time segment cost evaluation with all 6 physical factor scorers active.
- **Live Verification Results (18.50°N, 72.00°E)**:
  - Ocean Current: `0.36 knots` towards `126.6°` (Copernicus Marine)
  - Significant Wave ($H_s$): `2.46 meters`, `249.8°`, `9.8s` (Copernicus Marine)
  - Wind Speed: `15.90 knots` from `263.0°` (Open-Meteo)
  - Evaluated Segment Cost: `2.3894` (Navigable & Safe)

---

### Phase 6: Live Environmental Data Integration into GeographicGridGraph ✅ (Complete)

**Goal**: Make `GeographicGridGraph` capable of receiving real oceanographic and atmospheric conditions on every edge automatically, without coupling the routing algorithm to any external API.

#### Key Design Decisions
- **Midpoint Sampling**: Each directed edge `(s → t)` is sampled at its geographic midpoint `((lat_s+lat_t)/2, (lon_s+lon_t)/2)` — the best single-point representation of the environmental conditions experienced during the transit.
- **Dependency Injection**: `GeographicGridGraph.__init__` accepts an optional `environment_provider: WeatherProvider`. The graph holds a reference but never calls the provider directly during routing — only during explicit populate/refresh calls.
- **Strict Responsibility Separation**: Provider → EnvironmentalData → CostModel → GridEdge.cost → D* Lite. No layer is skipped or collapsed.
- **`GridEnvironmentUpdateError`**: Rich contextual error raised on provider failures, including source/target node IDs, midpoint lat/lon, and timestamp — enabling targeted retry or obstacle marking.

#### New Graph Methods
| Method | Description |
|---|---|
| `get_edge_midpoint(src_id, tgt_id)` | Returns geographic midpoint `(lat, lon)` of the directed edge |
| `populate_environment(timestamp, provider, ship, weights)` | Queries all navigable edges sequentially, populates `env_data`, recomputes costs |
| `refresh_edges(edges, timestamp, provider, ship, weights)` | Selective refresh — only the listed `(src, tgt)` pairs are updated |

#### Verification
- **80/80 offline unit tests pass** (8 new tests in `tests/test_grid_environment_integration.py`):
  - Provider injection, midpoint coordinate accuracy, explicit timestamps
  - Cost recalculation via CostModel on populated edges
  - Selective refresh: unrelated edges remain unchanged
  - Non-navigable obstacle edges skipped correctly
  - `GridEnvironmentUpdateError` raised on provider failure with full context
  - D* Lite plans optimal routes seamlessly on environment-populated grid

#### Live Integration Demo (`examples/run_live_grid_routing_demo.py`)
- **Grid**: 3×3, Arabian Sea corridor — `18.0°N–19.0°N, 71.0°E–72.0°E` (open water, no land mask)
- **Live Data**: All 24 directed edge midpoints populated from real Copernicus Marine + Open-Meteo data
- **Representative live edge conditions** (2026-08-15 12:00 UTC):

| Edge | Midpoint | Current | Wave Hs | Wind | Cost |
|---|---|---|---|---|---|
| node_0_0 → node_0_1 | 18.00N, 71.25E | 0.31 kn @ 136° | 2.42 m | 18.7 kn @ 261° | 2.4093 |
| node_1_1 → node_1_2 | 18.50N, 71.75E | 0.25 kn @ 125° | 2.49 m | 16.3 kn @ 262° | 2.3348 |
| node_1_2 → node_2_2 | 18.75N, 72.00E | 0.37 kn @ 123° | 2.47 m | 15.5 kn @ 262° | 2.5634 |

- **D* Lite optimal route**: `node_0_0 → node_0_1 → node_0_2 → node_1_2 → node_2_2`
- **Total accumulated cost**: `9.9162`, **Distance**: `117.14 NM`, **Estimated transit**: `6.51 hours`
- **Dijkstra oracle verification**: D* Lite cost = Dijkstra cost = `9.916245`, absolute delta = `0.000000e+00` ✅ **MATHEMATICAL MATCH**

---

### Phase 7: Dynamic Environmental Replanning (D* Lite Incremental Update) ✅ (Complete)

**Goal**: Connect the live environmental data pipeline to D* Lite's incremental repair engine so that environmental changes produce selective edge refreshes, and the same D* Lite planner instance incrementally replans without rebuilding the graph or resetting planner state.

#### New API: `EdgeRefreshResult`

Added to `naudisha/routing/graph.py`:

```python
@dataclass
class EdgeRefreshResult:
    source_id: str
    target_id: str
    old_cost: float
    new_cost: float
    old_env: Optional[EnvironmentalData]
    new_env: Optional[EnvironmentalData]
```

`refresh_edges()` now returns `List[EdgeRefreshResult]` instead of `None`. The routing layer uses this to call `dstar.update_edge()` on exactly the edges that changed, without touching any other planner state.

#### Dynamic Update Pipeline

```
Environmental update (LIVE or SIMULATED)
    -> graph.update_edge_environment() or graph.refresh_edges()
    -> EdgeRefreshResult (old_cost, new_cost, old_env, new_env)
    -> dstar.update_edge(source_id, target_id)  [per changed edge]
    -> dstar.replan()
    -> New optimal route
    -> Verify vs independent Dijkstra oracle
```

**Key invariants**:
- `GeographicGridGraph` is NOT rebuilt
- `DStarLite` is NOT reinstantiated
- `g`, `rhs`, `km` values are preserved and incrementally repaired
- Provider is NOT called during routing — only during explicit refresh/populate calls

#### Simulated Storm Methodology

The demo applies a deterministic storm scenario to a corridor:

```
Wind:    45 knots (headwind)
Waves:   5.5 m Hs (head seas)
Current: 2.5 knots (opposing)
```

This scenario is clearly labelled **[SIMULATED - NOT LIVE]** in all output.
Real Copernicus + Open-Meteo data is used for the initial grid and storm clearance (re-fetch).
No simulated values are presented as real observations.

#### Test Results: 100/100 Offline Tests Pass

20 new tests in `tests/test_dynamic_replanning.py`:

| # | Coverage |
|---|---|
| 1 | Initial route matches Dijkstra oracle |
| 2 | Cost increase causes route change |
| 3 | Cost decrease can restore preferred corridor |
| 4 | Storm causes detour route |
| 5 | Storm clearance restores original corridor |
| 6 | Simultaneous multi-edge updates handled correctly |
| 7 | Obstacle appearance causes route change |
| 8 | Obstacle disappearance allows route restoration |
| 9 | Only affected edges queried (call count check) |
| 10 | Unaffected edges remain unchanged |
| 11 | **D* Lite planner instance reused** (`id(dstar)` identical before/after) |
| 12 | Incremental result matches Dijkstra after update |
| 13 | Cost identity: `route_cost == sum(edge.cost)` |
| 14 | Unreachable state handled correctly |
| 15 | Unreachable state can become reachable |
| 16 | Provider failure does not partially corrupt graph |
| 17 | Failed refresh no silent data replacement |
| 18 | Timestamp forwarded correctly to provider |
| 19 | Both directed edges (A→B, B→A) handled independently |
| 20 | Floating-point comparison uses `abs_tol=1e-9` |

**Test count progression**: 80 → **100** (20 new, 0 regressions)

#### Live Demo (`examples/run_dynamic_replanning_demo.py`)

| Phase | Description |
|---|---|
| 1 | Grid specification (5×5, Arabian Sea) |
| 2 | Initial LIVE environment from Copernicus + Open-Meteo |
| 3 | Initial D* Lite optimal route + Dijkstra oracle |
| 4 | SIMULATED storm intercept (clearly labelled) |
| 5 | Incremental replan — same planner, no rebuild |
| 6 | Storm clearance (LIVE data re-fetched for cleared edges) |
| 7 | Second incremental replan + Dijkstra oracle |
| 8 | Performance timing: initial plan, storm replan, clearance replan |

---

### Phase 7.5: Batch CMEMS Environmental Sampling ✅ (Complete)

**Goal**: Reduce environmental data acquisition from O(N) network requests per grid edge to O(1) bounding-box queries, without changing routing mathematics.

#### Architecture Change

```
BEFORE (sequential):
    80 edges → 80 × (1 currents + 1 waves) = 160 CMEMS requests → ~8-10 minutes

AFTER (batch):
    80 edges → bounding box → 1 currents + 1 waves = 2 CMEMS requests → ~15-30 seconds
```

#### New Abstractions

| Type | Location | Purpose |
|---|---|---|
| `ConditionRequest` | `weather_provider.py` | Frozen dataclass: `(lat, lon, timestamp)` — hashable dict key |
| `BatchCapableProvider` | `weather_provider.py` | Separate ABC with `fetch_conditions_batch()` — not bolted onto `WeatherProvider` |

**Capability detection**: `isinstance(provider, BatchCapableProvider)` in `graph.py`.
Existing `WeatherProvider` is **unchanged** — full backward compatibility.

#### Provider Implementations

| Provider | Batch Strategy |
|---|---|
| `CopernicusMarineProvider` | Bounding-box subset query: `min/max(lats/lons) ± spatial_delta_deg` → 1 currents + 1 waves request → local L2 nearest-point extraction per midpoint |
| `CompositeEnvironmentalProvider` | Delegates CMEMS batch to `CopernicusMarineProvider.fetch_conditions_batch()`, deduplicates Open-Meteo by `round(lat,2), round(lon,2)` cell key (~4-8 unique HTTP requests for 80 midpoints) |

#### Temporal Bucketing

Requests are grouped by hour-bucket (`strftime("%Y-%m-%dT%H")`). Each bucket produces one pair of CMEMS requests. For typical grid population (single timestamp), this is exactly 1 bucket → 2 CMEMS calls total.

#### Test Results: 122/122 Offline Tests Pass

22 new tests in `tests/test_copernicus_batch_provider.py`:

| # | Coverage |
|---|---|
| 1 | `ConditionRequest` dataclass creation and hashability |
| 2 | Bounding box: `min(lats) - margin` to `max(lats) + margin` |
| 3 | Temporal range: `bucket_dt ± temporal_delta_hours` |
| 4 | ONE currents request for N points (same timestamp) |
| 5 | ONE waves request for N points (same timestamp) |
| 6 | Nearest-point extraction by L2 distance |
| 7 | Multiple coordinates receive correct nearest values |
| 8 | Multiple timestamps bucketed into separate CMEMS requests |
| 9-12 | Missing/NaN current and wave data error handling |
| 13 | Missing variable column error |
| 14 | Authentication failure maps to `CopernicusAuthenticationError` |
| 15 | Network failure maps to `CopernicusProviderError` |
| 16 | Cache prevents duplicate reader calls |
| 17 | Empty request list returns empty dict |
| 18 | Single-point batch matches `fetch_conditions()` |
| 19 | Coordinate validation |
| **20** | **REGRESSION/EQUIVALENCE: batch and per-edge produce identical edge costs** |
| **21** | **Graph batch: 24 edges → 2 reader calls (not 24×2)** |
| 22 | Non-batch provider falls back to per-edge path |

**Test count progression**: 100 → **122** (22 new, 0 regressions)

#### Benchmark Results (Deterministic)

| Grid | Edges | Old Requests | New Requests | Reduction | Equivalence |
|---|---|---|---|---|---|
| 3×3 | 24 | 48 | 2 | 24× | ✅ All costs match |
| 5×5 | 80 | 160 | 2 | 80× | ✅ All costs match |
| 10×10 | 360 | 720 | 2 | 360× | ✅ All costs match |

---

### Phase 8: Interactive Visual Dashboard & API (Upcoming) ⏳
- REST/WebSocket API for route planning requests and real-time voyage monitoring.
- Interactive map frontend displaying vessel trajectory, weather overlays, and dynamic route adjustments.
