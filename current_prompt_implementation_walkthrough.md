# Current Prompt: Phase 8.5 — Backend Contract Verification & Frontend Handoff Prep

## Goal

Perform a final verification pass to ensure that `docs/API_CONTRACT.md` accurately describes the actual backend implementation, every documented endpoint behaves according to contract, the test suite passes, and a concise frontend handoff document (`docs/FRONTEND_API_HANDOFF.md`) is created on `feature/backend-api`.

---

## 1. Branch

- **Working Branch**: `feature/backend-api` (Main remains untouched per instructions).

---

## 2. Work Performed

### 1. Contract-vs-Implementation Audit
- Audited all 7 documented endpoints against `docs/API_CONTRACT.md`:
  - `GET /health` — verified 200 OK and response shape.
  - `POST /api/ships` — verified ISO 8713 validation and response containing `ship` profile block with unit suffixes.
  - `POST /api/routes/preview` — verified optional `imo_number`, optional `departure_time`, optional `ship` particulars, `departure_time` echoing, and calculated `eta`.
  - `POST /api/ships/{imo_number}/tracking/start` — verified `destination` body schema and path IMO validation.
  - `GET /api/ships/{imo_number}/status` — verified status, position, destination, timestamp fields.
  - `GET /api/ships/{imo_number}/route` — verified route_status, route waypoints, statistics, destination, updated_at fields.
  - `WS /ws/ships/{imo_number}` — verified connection path, ISO 8713 validation, and connection closure on invalid IMO.
  - Error Envelope and HTTP Status Codes — verified HTTP 422 for `INVALID_IMO` and `INVALID_COORDINATES`.

### 2. Integration Tests Expansion
- Added WebSocket integration test cases in `tests/test_api.py` for valid IMO connection and invalid IMO rejection.
- Ran full test suite: **151 passed, 0 failures, 0 errors**.

### 3. Frontend Handoff Documentation
- Created `docs/FRONTEND_API_HANDOFF.md` containing:
  - Purpose & Authoritative Source note.
  - Base URLs for HTTP and WebSocket.
  - Endpoint Quick Reference table.
  - Frontend integration rules (strings for IMO, ISO 8713 check digit, UTC timestamps).
  - Route preview flow examples (With IMO vs Without IMO with ship particulars).
  - Key response fields explanation (`departure_time`, `eta`, `total_cost`).
  - Error handling table mapping error codes to UI actions.
  - WebSocket connection and message type details.
  - Documented MVP limitations (deferred features).

---

## 3. Files Modified

| File | Changes |
|---|---|
| `docs/FRONTEND_API_HANDOFF.md` | Created frontend integration and handoff guide for Contract v2 |
| `tests/test_api.py` | Added WebSocket integration tests (total 151 tests) |
| `current_prompt_implementation_walkthrough.md` | Updated walkthrough for Phase 8.5 |
