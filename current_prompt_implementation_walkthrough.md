# Current Prompt: Phase 8.3 — MVP API Contract v2 Finalization

## Goal

Review the existing API contract, the frontend addendum proposal, and the actual backend implementation, then produce ONE FINAL API CONTRACT that becomes the single source of truth for both frontend and backend.

---

## 1. Branch

- **Working Branch**: `feature/backend-api`
- No backend implementation changes in this phase — contract finalization only.

---

## 2. Work Performed

### Phase 1 — Inspected Current State

Read and cross-referenced every relevant file:

| File | Inspected For |
|---|---|
| `docs/API_CONTRACT.md` (v1) | Current contract promises |
| `docs/API_CONTRACT_ADDENDUM_PROPOSAL.md` | Frontend-raised gaps and proposals |
| `docs/FRONTEND_DEVELOPMENT_WORKFLOW.md` | Actual frontend flow requirements |
| `naudisha/api/schemas.py` | Pydantic models, IMO validation regex (`^\d{6,8}$`) |
| `naudisha/api/routes.py` | Controller wiring (timestamp NOT passed to service) |
| `naudisha/api/services.py` | Service layer (already accepts `timestamp`, hardcoded ShipProfile) |
| `naudisha/api/errors.py` | Error hierarchy and exception handlers |
| `naudisha/api/main.py` | FastAPI app factory |
| `naudisha/core/models.py` | ShipProfile (6 fields), EnvironmentalData, CostWeights |
| `naudisha/routing/graph.py` | 4-connected grid (DIRECTIONS_4), no land mask |
| `naudisha/data/weather_provider.py` | BatchCapableProvider interface |
| `tests/test_api.py` | 19 tests verifying current behavior |

### Phase 2 — Decided Each Proposal Item

| Item | Decision | Rationale |
|---|---|---|
| P0-1 `departure_time` | **ACCEPT** | Service already accepts timestamp; forecasts are time-dependent |
| P0-2 Ship particulars | **ACCEPT (simplified)** | Flat `ship` object, no `missing_fields`/`source` for MVP |
| P0-3 IMO-less routing | **ACCEPT** | `imo_number` optional on route preview |
| P1-1 Alerts | **DEFER** | WebSocket not implemented; no hazard detection logic exists |
| P1-2 Destination in tracking | **ACCEPT** | Frontend workflow requires displaying destination |
| P1-3 tracking/start body | **ACCEPT** | Backend needs destination to track |
| P1-4 ISO 8713 IMO | **ACCEPT** | Fixes 3-way validation disagreement |
| P2-1 /health | **ACCEPT** | Already implemented, frontend needs availability probe |
| P2-2 baseline_cost | **DEFER** | Requires computing second route; not MVP-essential |
| P2-3 legs array | **DEFER** | High value but not core MVP functionality |
| P2-4 timestamp default | **ACCEPT** | Backend fix; contract states "defaults to current UTC time" |
| P2-5 total_cost consistency | **ACCEPT** | Zero-distance returns 0.0, consistent with D* Lite path |
| 9.1 8-connected grid | **NOT CONTRACT** | Engine implementation detail |
| 9.2 Land mask | **NOT CONTRACT** | Engine implementation detail |

### Phase 3 — Wrote Final Contract

Replaced `docs/API_CONTRACT.md` with v2 containing 17 sections:

- §1 Base URL
- §2 Data Conventions (Coordinates, Timestamps, IMO with ISO 8713, ShipProfile with unit suffixes, Error Format)
- §3 GET /health
- §4 POST /api/ships (now includes `ship` block in response)
- §5 POST /api/routes/preview (now accepts optional `departure_time`, `ship`, nullable `imo_number`; response adds `departure_time`, `eta`)
- §6 POST /api/ships/{imo}/tracking/start (now requires `destination` body)
- §7 GET /api/ships/{imo}/status (now includes `destination`)
- §8 GET /api/ships/{imo}/route (now includes `destination`)
- §9 WebSocket /ws/ships/{imo} (documented connection, ordering, disconnect, cadence)
- §10 route_update message
- §11 position_update message
- §12 Reserved
- §13 Enumerations (ship status, route status, update reason)
- §14 Error Format
- §15 Error Codes (7 codes)
- §16 Responsibilities
- §17 Endpoint Summary

---

## 3. Files Modified

| File | Change |
|---|---|
| `docs/API_CONTRACT.md` | **Replaced** — complete rewrite as MVP API Contract v2 |
| `current_prompt_implementation_walkthrough.md` | Updated walkthrough for this phase |

---

## 4. Key Contract Changes from v1

1. `imo_number` is **optional** on `POST /api/routes/preview`
2. `departure_time` added as optional request field (defaults to current UTC)
3. `departure_time` and `eta` added to route preview response
4. `ship` object (ShipProfile) added as optional on route preview request
5. `ship` block added to `POST /api/ships` response
6. `destination` coordinate added to tracking/status/route responses
7. `POST /api/ships/{imo}/tracking/start` now requires a `destination` body
8. IMO validation standardized to ISO 8713 (exactly 7 digits with check digit)
9. `GET /health` formally documented
10. WebSocket behavior fully specified (connection, ordering, disconnect, cadence)
11. All enumerations collected in §13
12. Error codes collected in §15 with HTTP status mapping
