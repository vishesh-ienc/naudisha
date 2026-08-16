# Current Prompt: Phase 8.6 — Deploy Backend API & Prepare Final Frontend Access

## Goal

Deploy the NauDisha backend API from `feature/backend-api`, verify all MVP Contract v2 endpoints against the public server, and deliver the final frontend access details and handoff guide.

---

## 1. Branch

- **Working Branch**: `feature/backend-api` (Main remains untouched per instructions).

---

## 2. Work Performed

### 1. Server Deployment & Secure Public Tunneling
- Launched the FastAPI application via `uvicorn` on `0.0.0.0:8000`.
- Established a public HTTPS / WSS endpoint for remote access:
  - **HTTP Base URL**: `https://lemon-windows-taste.loca.lt`
  - **WebSocket Base URL**: `wss://lemon-windows-taste.loca.lt`
- Verified CORS middleware allowing frontend origins (e.g. `http://localhost:5173`) with preflight OPTIONS returning `Access-Control-Allow-Origin: http://localhost:5173`.

### 2. Live Public Endpoint Verification
Executed automated end-to-end verification against `https://lemon-windows-taste.loca.lt` testing:
1. `GET /health` -> `200 OK` (`{"status": "ok", "service": "naudisha-backend"}`)
2. `POST /api/ships` (Valid IMO `"1234567"`) -> `200 OK` (with `ship` profile block)
3. `POST /api/ships` (Invalid IMO Checksum `"1234560"`) -> `422 Unprocessable Content` (`INVALID_IMO`)
4. `POST /api/routes/preview` (With IMO & departure_time, live CMEMS+Open-Meteo) -> `200 OK` (`departure_time: 2026-08-20T06:00:00Z`, `eta: 2026-08-20T08:06:14Z`, `total_cost: 7.91`)
5. `POST /api/routes/preview` (IMO-less flow with custom ship particulars) -> `200 OK` (`imo_number: null`, `eta: 2026-08-16T11:54:13Z`, `total_cost: 7.38`)
6. `POST /api/routes/preview` (Missing IMO & Ship) -> `422` (`VALIDATION_ERROR`)
7. `POST /api/ships/1234567/tracking/start` -> `200 OK` (`tracking: true`)
8. `GET /api/ships/1234567/status` -> `200 OK` (with `destination`)
9. `GET /api/ships/1234567/route` -> `200 OK` (with `destination` and `route`)
10. `WS /ws/ships/1234567` -> Connected successfully; invalid IMO closed with policy violation.
11. CORS preflight OPTIONS & GET -> `200 OK` with `Access-Control-Allow-Origin`.

### 3. Frontend Handoff Guide Update
- Updated `docs/FRONTEND_API_HANDOFF.md` with:
  - Live public HTTP (`https://lemon-windows-taste.loca.lt`) and WebSocket (`wss://lemon-windows-taste.loca.lt`) URLs.
  - Frontend environment variable configuration (`VITE_BACKEND_URL=https://lemon-windows-taste.loca.lt`).
  - Endpoint quick reference table and request/response examples.

### 4. Tests
- Full test suite: **151 passed, 0 failed, 0 errors**.

---

## 3. Files Modified

| File | Changes |
|---|---|
| `docs/FRONTEND_API_HANDOFF.md` | Updated with public deployed API URL, WSS URL, and frontend env vars |
| `examples/verify_deployed_api.py` | Added automated verification suite for public endpoints, WebSocket, and CORS |
| `current_prompt_implementation_walkthrough.md` | Updated walkthrough for Phase 8.6 |
