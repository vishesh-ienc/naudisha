# Current Prompt: Dynamic Environmental Replanning (Phase 7)

## Goal

Connect the live environmental data pipeline to D* Lite's incremental repair engine,
completing the full dynamic routing loop:

```
INITIAL LIVE ENVIRONMENT
    -> INITIAL EDGE COSTS
    -> D* LITE OPTIMAL ROUTE
    -> ENVIRONMENT CHANGES (LIVE or SIMULATED)
    -> refresh_edges() -> EdgeRefreshResult
    -> dstar.update_edge()
    -> dstar.replan()  [same planner instance, no rebuild]
    -> NEW OPTIMAL ROUTE
    -> Verify vs independent Dijkstra oracle
```

---

## What Changed

### 1. `EdgeRefreshResult` dataclass (NEW — `naudisha/routing/graph.py`)

```python
@dataclass
class EdgeRefreshResult:
    source_id: str
    target_id: str
    old_cost: float       # Cost before environmental update
    new_cost: float       # Cost after environmental update
    old_env: Optional[EnvironmentalData]  # Environment before
    new_env: Optional[EnvironmentalData]  # Environment after
```

This is the **only new abstraction** in this phase. It is a lightweight value object — no logic, just data.

**Why**: The routing layer needs to know which specific edges changed and by how much, so it can call `dstar.update_edge()` on exactly those edges without touching the rest of the planner state.

---

### 2. `refresh_edges()` return type changed: `None` → `List[EdgeRefreshResult]`

Before refreshing each edge, captures `old_cost` and `old_env`. After refreshing, captures `new_cost` and `new_env`. Returns one result per requested edge.

Callers that previously ignored the return value are unaffected (Python silently discards it).

On provider failure: graph state is NOT modified for the failing edge (old values preserved). `GridEnvironmentUpdateError` is re-raised immediately.

---

### 3. D* Lite: unchanged

`dstar_lite.py` has **zero changes**. The planner already exposes:
- `update_edge(source_id, target_id)` — O(1) vertex update
- `update_edges(edges)` — batch update
- `replan()` — incremental `compute_shortest_path()` + path extraction

---

## Dynamic Update Pipeline (Caller Code Pattern)

```python
# 1. Obtain changed edges from environment event (e.g. storm)
results = graph.refresh_edges(
    edges=affected_edge_pairs,
    timestamp=new_timestamp,
    provider=storm_provider,
    ship=ship,
)

# 2. Notify D* Lite of exactly the changed edges
for result in results:
    dstar.update_edge(result.source_id, result.target_id)

# 3. Incremental replan — same planner object, g/rhs/km preserved
new_route = dstar.replan()
```

No graph rebuild. No planner reset. No Dijkstra used as the actual planner.

---

## Test Suite: 100/100 Pass (20 New Tests)

All 20 tests in `tests/test_dynamic_replanning.py` are completely offline and deterministic.

| # | Test | Key Assertion |
|---|---|---|
| 1 | Initial route matches Dijkstra | `abs(dstar_cost - dijkstra_cost) < 1e-9` |
| 2 | Cost increase changes route | Route or cost differs after storm |
| 3 | Cost decrease restores corridor | `cleared_cost <= storm_cost` |
| 4 | Storm causes detour | Detour reaches goal |
| 5 | Storm clearance restores route | `restored_cost == initial_cost` |
| 6 | Multiple simultaneous updates | Dijkstra oracle matches after batch |
| 7 | Obstacle causes route change | Blocked node absent from new route |
| 8 | Obstacle removal restores route | `restored_cost == initial_cost` |
| 9 | Only affected edges queried | `len(call_log) == 1` |
| 10 | Unaffected edges unchanged | `cost_before == cost_after` |
| **11** | **Planner instance reused** | `id(dstar) before == id(dstar) after` |
| 12 | Incremental = Dijkstra after update | `abs_tol=1e-9` |
| 13 | Cost identity | `get_path_cost() == sum(edge.cost)` |
| 14 | Unreachable → empty route + inf cost | |
| 15 | Unreachable → reachable after update | |
| 16 | Provider failure → graph unchanged | `edge.cost` and `edge.env_data` unchanged |
| 17 | No silent fake data on failure | `env_data is original_env` |
| 18 | Timestamp forwarded to provider | `call_log == [new_timestamp]` |
| 19 | A→B and B→A independent | Only 1 provider call for single-edge refresh |
| 20 | FP tolerance `abs_tol=1e-9` | Identical env produces identical cost |

---

## Live Demo: `examples/run_dynamic_replanning_demo.py`

7-phase demo on a 5×5 Arabian Sea grid:

| Phase | Data Source | Description |
|---|---|---|
| 1 | — | Grid specification |
| 2 | **LIVE** | Copernicus Marine + Open-Meteo initial grid population |
| 3 | **LIVE** | Initial D* Lite route + Dijkstra oracle |
| 4 | **SIMULATED** | Storm: 45 kn wind, 5.5 m waves, 2.5 kn opposing current |
| 5 | — | Same planner reused: incremental replan after storm |
| 6 | **LIVE** | Storm cleared: live data re-fetched for storm-affected edges |
| 7 | — | Second incremental replan + Dijkstra oracle |
| 8 | — | Timing: initial, storm replan, clearance replan |

All simulated data is clearly labelled `[DATA SOURCE: SIMULATED - NOT LIVE]`.
No fabricated values are presented as real Copernicus/Open-Meteo observations.

---

## Files Changed

| File | Change |
|---|---|
| `naudisha/routing/graph.py` | Added `EdgeRefreshResult` dataclass; updated `refresh_edges()` to return `List[EdgeRefreshResult]`; added `Union`, `datetime` imports |
| `naudisha/routing/__init__.py` | Exported `EdgeRefreshResult` |
| `naudisha/__init__.py` | Exported `EdgeRefreshResult` |
| `tests/test_dynamic_replanning.py` | NEW — 20 offline tests |
| `examples/run_dynamic_replanning_demo.py` | NEW — 7-phase live demo |
| `PROGRESS.md` | Phase 7 section added |

**Previous test count**: 80  
**New test count**: 100  
**Regressions**: 0
