# Current Prompt: Phase 8.1 — Backend API Foundation

## Goal

Initialize the foundation for the NauDisha Backend REST API, strictly adhering to `docs/API_CONTRACT.md` and `docs/FRONTEND_DEVELOPMENT_WORKFLOW.md`. The backend API acts as an adapter layer around the existing NauDisha routing and environmental engine without modifying or reimplementing any core mathematics.

```
USER / FRONTEND
       ↓
   BACKEND API (FastAPI + Pydantic)
       ↓
ROUTE PLANNING SERVICE (RoutePlanningService)
       ↓
EXISTING NAUDISHA ENGINE
       ↓
Environmental Data (Copernicus + Open-Meteo)
       ↓
CostModel
       ↓
GeographicGridGraph
       ↓
D* Lite Pathfinding
       ↓
OPTIMAL ROUTE RESULT
       ↓
JSON RESPONSE (Contract-compliant)
```

---

## 1. Branch Strategy

- **Working Branch**: `feature/backend-api`
- Tracked on remote: `origin/feature/backend-api`
- `main` branch remains untouched.

---

## 2. API Framework & Setup

- **Framework**: **FastAPI** (`0.136.1`) with **Pydantic** (`v2`) and **Uvicorn** (`0.46.0`).
- **Entrypoint**: `naudisha/api/main.py` -> `uvicorn naudisha.api.main:app --reload`.
- **CORS**: Configured with permissive defaults (`allow_origins=["*"]`) for frontend client development.

---

## 3. Endpoints Implemented

| Method | Path | Description | Status Code | API Contract Ref |
|---|---|---|---|---|
| `GET` | `/health` | Lightweight service health probe | `200 OK` | Section 6 |
| `POST` | `/api/routes/preview` | Planned voyage optimal route calculation | `200 OK` | Section 5 |
| `POST` | `/api/ships` | Vessel identification endpoint for MVP | `200 OK` | Section 4 |

---

## 4. Architectural Separation

```
[ HTTP / Controller Layer ] (naudisha/api/routes.py, main.py)
            │
            ▼
[ Schema & Validation Layer ] (naudisha/api/schemas.py, errors.py)
            │
            ▼
[ Service Orchestration Layer ] (naudisha/api/services.py: RoutePlanningService)
            │
            ▼
[ Domain Routing Core ] (GeographicGridGraph, CostModel, DStarLite)  <-- ZERO MODIFICATIONS
```

### Key Design Principles:
1. **No Routing Math in API Controllers**: All routing logic, grid building, coordinate snapping, and D* Lite invocations live in `RoutePlanningService`.
2. **Dependency Injection**: `get_route_service()` is provided via FastAPI `Depends()`, enabling 100% offline unit and integration tests by swapping providers.
3. **Standardized Error Envelope**: Every error matches `{ "error": { "code": "...", "message": "..." } }`.
4. **Standard Error Codes**: `INVALID_IMO`, `INVALID_COORDINATES`, `ROUTE_NOT_FOUND`, `ENVIRONMENT_UNAVAILABLE`, `TRACKING_UNAVAILABLE`, `SHIP_NOT_FOUND`, `INTERNAL_ERROR`.

---

## 5. Core Invariant: Zero Touch to Routing Engine

- **D* Lite Algorithm** (`naudisha/routing/dstar_lite.py`): **0 lines changed**
- **GeographicGridGraph** (`naudisha/routing/graph.py`): **0 lines changed**
- **CostModel & Scorers** (`naudisha/cost/`): **0 lines changed**
- **Copernicus & Open-Meteo Providers** (`naudisha/data/`): **0 lines changed**

---

## 6. Test Suite: 138/138 Passing (16 New Tests)

Run command:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Coverage in `tests/test_api.py`:

| # | Test Case | Target Verification | Status |
|---|---|---|---|
| 1 | `test_01_health_endpoint` | `GET /health` returns `{"status": "ok", "service": "naudisha-backend"}` | ✅ PASS |
| 2 | `test_02_valid_route_preview` | `POST /api/routes/preview` returns valid route array and voyage metrics | ✅ PASS |
| 3 | `test_03_invalid_latitude_out_of_bounds` | Latitude > 90 returns 422 with `INVALID_COORDINATES` | ✅ PASS |
| 4 | `test_04_invalid_longitude_out_of_bounds` | Longitude > 180 returns 422 with `INVALID_COORDINATES` | ✅ PASS |
| 5 | `test_05_missing_destination_field` | Missing `destination` object returns 422 validation error | ✅ PASS |
| 6 | `test_06_missing_imo_number` | Missing `imo_number` returns 422 `INVALID_IMO` | ✅ PASS |
| 7 | `test_07_invalid_imo_format_alphabetic` | Alphabetic IMO string returns 422 `INVALID_IMO` | ✅ PASS |
| 8 | `test_08_invalid_imo_format_too_short` | Short IMO (< 6 digits) returns 422 `INVALID_IMO` | ✅ PASS |
| 9 | `test_09_dependency_injection_custom_provider` | Injected mock provider runs route calculation offline | ✅ PASS |
| 10 | `test_10_response_serialization_fields_match_contract` | JSON keys strictly match `docs/API_CONTRACT.md` Section 5 | ✅ PASS |
| 11 | `test_11_environment_unavailable_error_mapped` | `EnvironmentUnavailableError` maps to 503 response | ✅ PASS |
| 12 | `test_12_route_not_found_error_mapped` | `RouteNotFoundError` maps to 404 response | ✅ PASS |
| 13 | `test_13_unhandled_exception_maps_to_500_internal_error` | Uncaught errors return clean 500 without leaking stack traces | ✅ PASS |
| 14 | `test_14_service_direct_planning` | Direct domain service calculation returns `RoutePlanResult` | ✅ PASS |
| 15 | `test_15_service_same_start_and_destination` | Identical start/destination returns 0 distance/cost | ✅ PASS |
| 16 | `test_16_ship_identify_endpoint` | `POST /api/ships` returns vessel position matching contract | ✅ PASS |

**Previous test count**: 122  
**New test count**: 138 (16 new, 0 regressions)

---

## 7. Files Created & Modified

| File | Change |
|---|---|
| `naudisha/api/main.py` | **NEW** — FastAPI app factory, CORS, exception handlers, router bindings |
| `naudisha/api/schemas.py` | **NEW** — Pydantic models for Coordinate, IMO, Health, Route Preview, Ship, Errors |
| `naudisha/api/errors.py` | **NEW** — Custom domain/API exception classes and Starlette/FastAPI handlers |
| `naudisha/api/services.py` | **NEW** — `RoutePlanningService` and `RoutePlanResult` domain orchestration |
| `naudisha/api/routes.py` | **NEW** — Controller endpoints (`/health`, `/api/routes/preview`, `/api/ships`) |
| `naudisha/api/__init__.py` | Exported public API classes, models, and services |
| `pyproject.toml` | Added `pydantic>=2.0.0` and `api` optional dependencies |
| `tests/test_api.py` | **NEW** — 16 offline unit and integration tests |
| `PROGRESS.md` | Documented Phase 8.1 milestone and test progression |
