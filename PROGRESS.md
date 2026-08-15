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

### Phase 4: Copernicus Marine Service Integration & Discovery ✅ (In Progress)
**Status**: Access Configured & Datasets Identified

- **Architecture Strategy Evolution**:
  - **OLD Strategy**: Open-Meteo planned as primary marine & weather source.
  - **NEW Strategy**: **Copernicus Marine Service (CMEMS)** is the primary oceanographic data source. A separate free weather provider (e.g. NOAA GFS / Open-Meteo) will be integrated in a later step to supply complementary wind data.
  - **Why the change was made**: Copernicus Marine is the official European earth observation programme for oceanography, providing high-resolution physics-based analysis and forecasting models (NEMO, WaveWatch III, MFWAM) with in-situ Argo float and satellite altimetry assimilation. It offers dedicated, research-grade eastward/northward ocean currents (`uo`, `vo`) and full spectral wave parameters (`VHM0`, `VMDR`, `VTPK`).
- **Provider Abstraction Intact**:
  - Kept `WeatherProvider` interface completely decoupled from specific data backends.
  - D* Lite, `GeographicGridGraph`, `CostModel`, and scoring formulas remain 100% unchanged.
- **Toolbox Configuration & Authentication**:
  - Installed official `copernicusmarine` toolbox (v2.4.1).
  - Authenticated via local credential configuration (zero credentials stored in repository or logged).
  - Configured `.gitignore` to prevent any accidental credential or raw NetCDF/GRIB commits.
- **Discovered & Verified Copernicus Datasets**:
  1. **Ocean Currents (Physics)**:
     - **Product ID**: `GLOBAL_ANALYSISFORECAST_PHY_001_024`
     - **Dataset ID**: `cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i`
     - **Variables**: `uo` (Eastward water velocity, $m/s$), `vo` (Northward water velocity, $m/s$)
     - **Depth**: `depth = 0.494m` (Surface layer)
     - **Spatial Resolution**: $0.083^\circ \times 0.083^\circ$ (~9 km / $1/12^\circ$), Global coverage including Indian Ocean
     - **Temporal Resolution**: 6-hourly instantaneous
     - **Alternative Hourly Dataset**: `cmems_mod_glo_phy_anfc_merged-uv_PT1H-i` (1-hourly surface total UV)
  2. **Ocean Waves**:
     - **Product ID**: `GLOBAL_ANALYSISFORECAST_WAV_001_027`
     - **Dataset ID**: `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`
     - **Variables**: `VHM0` (Spectral significant wave height, $m$), `VMDR` (Mean wave direction, $^\circ$), `VTPK` (Peak wave period, $s$)
     - **Spatial Resolution**: $0.083^\circ \times 0.083^\circ$ (~9 km)
     - **Temporal Resolution**: 3-hourly instantaneous
- **Variable Mapping Schema to `EnvironmentalData`**:
  - Current Speed: $v_{\text{knots}} = \sqrt{u_o^2 + v_o^2} \times 1.943844$ ($1\text{ m/s} = 1.943844\text{ kn}$)
  - Current Direction: $\theta_{\text{flow}} = (90^\circ - \text{atan2}(v_o, u_o) \cdot \frac{180}{\pi} + 360^\circ) \pmod{360^\circ}$ (oceanographic flow heading)
  - Wave Height: `VHM0` ($m$)
  - Wave Direction: `VMDR` ($^\circ$)
  - Wave Period: `VTPK` ($s$)
  - Wind Speed & Direction: Sourced from complementary atmospheric provider in future step.
- **Verification & Testing**:
  - Added schema specifications and vector conversion helpers in [`naudisha/data/copernicus_schema.py`](file:///c:/Users/VISHESH/Desktop/naudisha/naudisha/data/copernicus_schema.py).
  - Added 6 offline unit tests in [`tests/test_copernicus_metadata.py`](file:///c:/Users/VISHESH/Desktop/naudisha/tests/test_copernicus_metadata.py) (57/57 total unit tests passing).
  - Created [`examples/verify_copernicus_access.py`](file:///c:/Users/VISHESH/Desktop/naudisha/examples/verify_copernicus_access.py) to inspect catalogue metadata and demonstrate vector conversions live.

---

### Phase 5: Interactive Visual Dashboard & API (Upcoming) ⏳
- REST/WebSocket API for route planning requests and real-time voyage monitoring.
- Interactive map frontend displaying vessel trajectory, weather overlays, and dynamic route adjustments.
