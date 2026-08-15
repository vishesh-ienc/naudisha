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

### Phase 4: Marine Data Integration & Dynamic Adapters (Next) ⏳
- Ingest real meteorological and oceanographic raster/GRIB data (Copernicus Marine, NOAA WW3/GFS).
- Interpolate dynamic weather grids onto the navigation graph.

---

### Phase 5: Interactive Visual Dashboard & API (Upcoming) ⏳
- REST/WebSocket API for route planning requests and real-time voyage monitoring.
- Interactive map frontend displaying vessel trajectory, weather overlays, and dynamic route adjustments.
