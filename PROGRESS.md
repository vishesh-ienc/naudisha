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

### Phase 6: Interactive Visual Dashboard & API (Upcoming) ⏳
- REST/WebSocket API for route planning requests and real-time voyage monitoring.
- Interactive map frontend displaying vessel trajectory, weather overlays, and dynamic route adjustments.
