# NauDisha — Codebase & Backend/Frontend Integration Review

**Date:** August 16, 2026  
**Status:** Complete Technical Audit  
**Scope:** Backend Routes, Service Layer, Dynamic Routing Engine ($D^*$ Lite), Concurrency Architecture, WebSocket Navigation Simulator, Frontend Resilient API Layer, TypeScript Type System, and Integration End-to-End.

---

## 1. Executive Summary

A comprehensive architectural and integration audit was conducted following the synchronization of the latest backend and frontend commits (`origin/main`). 

### Core Audit Outcomes:
1. **Backend Verification:** **211 of 211 unit and integration tests passed** in 5.92s across all core modules (`core/dstar_lite`, `core/cost_model`, `data/copernicus`, `data/aisstream`, `api/routes`, `api/planning`, `api/tracking`).
2. **Endpoint Coverage:** All 10 defined HTTP endpoints and WebSocket streams adhere strictly to **API Contract v2** (`docs/API_CONTRACT.md`) and the asynchronous planning addendum.
3. **Resilience Strategy:** The frontend incorporates an enterprise-grade 3-tier fallback architecture (**Live WebSocket $\rightarrow$ REST Polling $\rightarrow$ Labelled Simulation**) backed by runtime Zod schema validation and a telemetry event bus.
4. **Actionable Finding:** The frontend codebase references several internal helper modules in `frontend/src/lib/` (`utils.ts`, `format.ts`, `geo.ts`, `imo.ts`, `explain.ts`, `ports.ts`) that were omitted during recent git commits, preventing clean TypeScript bundle compilation (`tsc -b`).

---

## 2. Backend Route Verification & Test Status

The backend is built on **FastAPI** with modular routers (`health_router`, `api_router`, `ws_router`) and exception handlers translating domain and validation exceptions into standard contract error envelopes (`{ "error": { "code": "...", "message": "..." } }`).

### 2.1 Complete Endpoint Audit Matrix

| Method | Path | Summary / Description | Backend Handler | Unit Test Coverage | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Liveness check returning service status without querying third parties. | `routes.py:get_health` | `test_api.py:test_health_endpoint` | **Working** |
| `GET` | `/ready` | Deep readiness probe reporting Copernicus & AISStream availability. | `routes.py:get_ready` | `test_api.py:test_readiness_probe` | **Working** |
| `POST` | `/api/ships` | Identify vessel by ISO 8713 7-digit IMO number. Returns particulars & AIS fix. | `routes.py:identify_ship` | `test_api.py:test_identify_ship_*` | **Working** |
| `POST` | `/api/routes/preview` | Synchronous optimal route calculation with per-leg weather and cost metrics. | `routes.py:preview_route` | `test_api.py:test_preview_route_*` | **Working** |
| `POST` | `/api/routes/plan` | Queue asynchronous route plan in worker pool; returns `202 Accepted` job handle. | `routes.py:submit_route_plan` | `test_api.py:test_async_route_plan_*` | **Working** |
| `GET` | `/api/routes/plan/{job_id}` | Poll asynchronous planning status (`planning` \| `ready` \| `failed`). | `routes.py:get_route_plan` | `test_api.py:test_poll_route_plan_*` | **Working** |
| `POST` | `/api/ships/{imo}/tracking/start` | Start live tracking session; triggers background route calculation. | `routes.py:start_tracking` | `test_tracking.py:test_start_tracking_*` | **Working** |
| `POST` | `/api/ships/{imo}/tracking/stop` | Stop live tracking session (idempotent 200). | `routes.py:stop_tracking` | `test_tracking.py:test_stop_tracking_*` | **Working** |
| `GET` | `/api/ships/{imo}/status` | Query current dead-reckoned coordinates, status, and active destination. | `routes.py:get_ship_status` | `test_tracking.py:test_ship_status_*` | **Working** |
| `GET` | `/api/ships/{imo}/route` | Query active remaining route (consumed waypoints automatically pruned). | `routes.py:get_ship_route` | `test_tracking.py:test_ship_route_*` | **Working** |
| `WS` | `/ws/ships/{imo}` | Real-time push channel streaming `route_update` and `position_update`. | `routes.py:websocket_ship_endpoint` | `test_tracking.py:test_websocket_*` | **Working** |

---

## 3. Backend Subsystem Architecture

```
                                  +-----------------------------+
                                  |    FastAPI Routers & Handlers|
                                  +--------------+--------------+
                                                 |
                         +-----------------------+-----------------------+
                         |                                               |
             +-----------v-----------+                       +-----------v-----------+
             |   PlanningManager     |                       | TrackingSessionManager|
             |   (ThreadPoolExecutor)|                       | (Asyncio Ticker Task) |
             +-----------+-----------+                       +-----------+-----------+
                         |                                               |
                         +-----------------------+-----------------------+
                                                 |
                                  +--------------v--------------+
                                  |    RoutePlanningService     |
                                  +--------------+--------------+
                                                 |
                     +---------------------------+---------------------------+
                     |                           |                           |
         +-----------v-----------+   +-----------v-----------+   +-----------v-----------+
         |    D* Lite Router     |   | Multi-Factor Cost     |   | Environmental & Vessel|
         |  (Dynamic Replanning) |   | (Hydrodynamics/Safety)|   | Data Providers (CMEMS)|
         +-----------------------+   +-----------------------+   +-----------------------+
```

### 3.1 Asynchronous Planning Engine (`backend/naudisha/api/planning.py`)
- **Challenge:** Fetching netCDF environmental forecast data for currents and wave fields from Copernicus Marine takes 75–85s on cold requests. Direct HTTP preview requests can exceed browser timeout ceilings.
- **Solution:** `POST /api/routes/plan` queues the job on a `ThreadPoolExecutor` (up to 4 concurrent plans).
- **Deduplication:** Clients querying identical voyage parameters (`signature` = rounded origin/dest/time) attach to existing in-flight jobs, avoiding duplicate upstream CMEMS loads.
- **Result Cache:** Completed plans are cached for 30 minutes (`RESULT_CACHE_TTL_SECONDS = 1800s`), enabling sub-second response on repeated queries.

### 3.2 Live Navigation Simulator (`backend/naudisha/api/tracking.py`)
- **Central Ticker:** A single background `asyncio` task steps all active tracked voyages at 3.0s real-time intervals (`TICK_SECONDS = 3.0`), compressed by a 60x simulation factor (`TIME_SCALE = 60.0`).
- **Dynamic Replanning:** When a vessel makes significant progress along the path or weather forecast boundaries refresh (`REPLAN_INTERVAL_SECONDS = 45s`), background replanning is triggered from the vessel's current position.
- **Thread Safety:** Cross-thread delivery from planning worker threads to client WebSocket queues on the asyncio loop uses `sub.loop.call_soon_threadsafe(_offer, ...)`.

---

## 4. Frontend Integration & Resilience Architecture

The frontend is implemented with **React 19**, **Vite 8**, **TypeScript**, and **Tailwind CSS v4**.

```
                        +---------------------------------------+
                        |        UI Components & Pages          |
                        | (PlanVoyagePage, TrackShipPage, Maps) |
                        +-------------------+-------------------+
                                            |
                        +-------------------v-------------------+
                        |         Resilient API Layer           |
                        |      (services/resilientApi.ts)       |
                        +---------+-------------------+---------+
                                  |                   |
            +---------------------v-----+       +-----v---------------------+
            | Live Transport            |       | Fallback Engine           |
            | (apiClient.ts / WebSocket)|       | (Mock Fixtures & Sim)     |
            +-------------+-------------+       +-------------+-------------+
                          |                                   |
            +-------------v-------------+                     |
            | Zod Runtime Schema Guard  |                     |
            | (services/schemas.ts)     |                     |
            +-------------+-------------+                     |
                          |                                   |
                          +-----------------+-----------------+
                                            |
                               +------------v------------+
                               | In-Memory Telemetry Bus |
                               |  (DataSourceConsole)    |
                               +-------------------------+
```

### 4.1 Resilient Execution Strategy
1. **Never Mask Input Errors:** On 4xx errors (invalid IMO check digit, out-of-bounds coordinates, or semantic 404), the API error is surfaced directly to the user rather than faking a success.
2. **Graceful Fallback on Network / Server Outages:** On 5xx, backend unreachability, or schema contract violations, the UI transparently transitions to mock data with a visible `MOCK` badge.
3. **Telemetry & Devtools:** Every HTTP and WebSocket message, latency metric, and fallback reason is logged to `telemetry.ts` and visible in real time inside `DataSourceConsole.tsx`.

### 4.2 WebSocket Reconnection & Synchronization
- `LiveSocket` manages exponential backoff with jitter.
- Enforces message ordering using ISO timestamps to drop delayed duplicate packets.
- On reconnect, automatically executes a REST sync (`syncOnce`) querying `GET /status` and `GET /route` to catch up on state changes per Contract §9.

---

## 5. Discrepancies & Build Issues Identified

During code review and execution of `npm run build`, the following specific issues were detected in the frontend codebase:

### 5.1 Missing Utility Modules in `frontend/src/lib/`
Recent UI components (`LocationSearch.tsx`, `RouteExplanation.tsx`, `LocationPicker.tsx`, `ShipParticularsForm.tsx`, etc.) import utility functions that were not committed to the repository:

1. **`src/lib/utils.ts`**:
   - `cn(...inputs)`: Tailwind class merger using `clsx` and `tailwind-merge`.
   - `uid(prefix)`: Unique ID generator for telemetry events.
2. **`src/lib/format.ts`**:
   - `formatDistance(nm)`: Nautical miles formatting.
   - `formatDuration(hours)`: Human-readable hours/minutes formatting.
   - `formatTimestamp(iso)`: Date/time formatting.
   - `formatCoordinate(coord, precision)`: Decimal degrees / DMS formatting.
   - `compassPoint(bearing)`: N, NE, E, SE, S, SW, W, NW conversion.
   - `relativeTime(timestamp)`: "2 mins ago" formatting.
   - `toDatetimeLocalValue(date)`: `<input type="datetime-local">` value formatter.
3. **`src/lib/geo.ts`**:
   - `haversineNm(c1, c2)`: Great-circle distance calculation in nautical miles.
   - `bearingDeg(c1, c2)`: Initial bearing in degrees [0, 360).
   - `pointAlongPath(path, distanceNm)`: Waypoint interpolation and segment detection.
   - `boundsOf(coords)`: Leaflet `LatLngBoundsExpression` generator.
   - `smoothPath(coords)`: Catmull-Rom or Bezier polyline smoothing.
   - `validateSelectionPoint(coord)`: Sea coordinate bounds validation.
   - `NAVIGABLE_REGION`, `PRESET_LOCATIONS`: Mumbai approach corridor constants.
4. **`src/lib/imo.ts`**:
   - `validateImo(imo)`: ISO 8713 check digit validator.
   - `normalizeImo(str)`: Clean numeric string extractor.
   - `SAMPLE_IMO_NUMBERS`: Verified demo vessel IMO list.
5. **`src/lib/explain.ts`**:
   - `describeLeg(leg)`: Textual summary of wind/current impact on a leg.
   - `legInfluence(leg, allLegs)`: Classifies segment as `favourable`, `neutral`, or `adverse`.
   - `summariseFactors(legs)`: Aggregates dominant environmental factors across the route.
   - `summariseRoute(route, legs)`: High-level natural language summary of route choice.
6. **`src/lib/ports.ts`**:
   - `NAMED_LOCATIONS`: Approach waypoints for major regional ports.
   - `searchLocations(query)`: Fuzzy search by port/country name.
   - `nearestLocationName(coord)`: Reverse lookup of closest named waypoint.

### 5.2 Type Definitions & Strict TypeScript Alignment
- **`ShipParticulars`**: Alias for `ShipProfile` (with partial/nullable fields for manual entry forms) needed in `frontend/src/types/api.ts`.
- **`RouteAlert`**: Interface representing storm/hazard warnings needed in `frontend/src/types/api.ts`.
- **`baseline_cost`**: Optional property on `RoutePreviewResponse` and `CurrentRouteResponse`.
- **Strict Index Typing in `RouteExplanation.tsx`**: Implicit `any` and undefined index errors on `FACTOR_ICON` and `INFLUENCE_STYLE`.

---

## 6. Actionable Remediation Plan

To bring the codebase into 100% clean compilation and end-to-end working order, the following sequential actions should be performed:

1. **Create Missing Library Files:**
   - Implement `frontend/src/lib/utils.ts`
   - Implement `frontend/src/lib/format.ts`
   - Implement `frontend/src/lib/geo.ts`
   - Implement `frontend/src/lib/imo.ts`
   - Implement `frontend/src/lib/explain.ts`
   - Implement `frontend/src/lib/ports.ts`

2. **Update Type Definitions & Schemas:**
   - Add `ShipParticulars`, `RouteAlert`, and optional `baseline_cost` to `frontend/src/types/api.ts`.
   - Fix mock fixture typing in `frontend/src/services/mock/fixtures.ts`.

3. **Verify Build & Run Servers:**
   - Run `npm run build` in `frontend/` to confirm 0 TypeScript errors.
   - Launch backend API with `uvicorn naudisha.api.main:app --port 8000`.
   - Launch frontend dev server with `npm run dev`.

---

*Report prepared by Antigravity AI Codebase Analysis Subsystem.*
