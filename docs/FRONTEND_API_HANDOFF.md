# NauDisha — Frontend API Handoff Document

**Target:** Frontend Development Team  
**API Version:** MVP Contract v2  
**Authoritative Specification:** [`docs/API_CONTRACT.md`](./API_CONTRACT.md)  
**Status:** Deployed & Verified for Frontend Access  
**Working Branch:** `feature/backend-api`

---

## 1. Purpose

This document provides a concise integration guide for the frontend team to connect UI components and services with the NauDisha backend. It summarizes endpoint behaviors, data models, user flows, and error handling conventions established in **MVP API Contract v2**.

> [!IMPORTANT]
> [`docs/API_CONTRACT.md`](./API_CONTRACT.md) is the **single authoritative source of truth**. If this handoff guide ever differs in detail from `API_CONTRACT.md`, the contract document takes precedence.

---

## 2. API Access & Base URLs

### Live Deployed Backend (Public Remote Access)
- **HTTP Base URL:** `https://lemon-windows-taste.loca.lt`
- **WebSocket Base URL:** `wss://lemon-windows-taste.loca.lt`

### Local Development Backend
- **HTTP Base URL:** `http://localhost:8000`
- **WebSocket Base URL:** `ws://localhost:8000`

All endpoints are relative to the base URL. All API routes are prefixed with `/api` except `/health` and the WebSocket endpoint `/ws/ships/{imo_number}`.

---

## 3. Frontend Environment Configuration

In your frontend `.env` (or `.env.local`), configure:

```env
# Point Vite proxy or API client to the backend instance:
VITE_BACKEND_URL=https://lemon-windows-taste.loca.lt
VITE_API_BASE_URL=https://lemon-windows-taste.loca.lt
```

*(For local testing without the tunnel, set `VITE_BACKEND_URL=http://localhost:8000`)*

---

## 4. Endpoint Quick Reference

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| `GET` | `/health` | Backend availability probe | ✅ Live & Verified |
| `POST` | `/api/ships` | Identify vessel by IMO | ✅ Live & Verified (Demo) |
| `POST` | `/api/routes/preview` | Calculate optimal environmental route | ✅ Live & Verified (Real D* Lite) |
| `POST` | `/api/ships/{imo_number}/tracking/start` | Begin vessel tracking | ✅ Live & Verified |
| `GET` | `/api/ships/{imo_number}/status` | Query current ship position & destination | ✅ Live & Verified |
| `GET` | `/api/ships/{imo_number}/route` | Query current active optimal route | ✅ Live & Verified |
| `WS` | `/ws/ships/{imo_number}` | Real-time position & route updates | ✅ Live & Verified |

---

## 5. Frontend Integration Notes

1. **IMO Numbers are Strings:** Always transmit IMO numbers as strings of exactly 7 digits (e.g. `"1234567"`). Never cast them to integers.
2. **ISO 8713 Validation:** IMO numbers use the ISO 8713 check-digit rule:
   - Must be 7 numeric digits.
   - The 7th digit equals: `(d[0]*7 + d[1]*6 + d[2]*5 + d[3]*4 + d[4]*3 + d[5]*2) % 10`.
   - The frontend can validate this on input to give immediate visual feedback.
3. **Coordinates:** Always format as `{ "latitude": float, "longitude": float }` with latitude in `[-90, 90]` and longitude in `[-180, 180]`.
4. **Timestamps:** Always use ISO-8601 UTC with `Z` suffix (e.g. `"2026-08-20T06:00:00Z"`).
5. **Single Source of Truth:**
   - The frontend **MUST NOT** calculate marine routes, compute D* Lite paths, or evaluate environmental costs.
   - The frontend **MUST NOT** query Copernicus Marine Service or Open-Meteo directly.
   - All routing and meteorological analysis is handled exclusively by the backend.

---

## 6. Route Preview Flows

The `POST /api/routes/preview` endpoint supports two distinct user flows:

### Flow A: With IMO Number (Known Vessel)

```json
{
  "imo_number": "1234567",
  "start": { "latitude": 18.52, "longitude": 72.91 },
  "destination": { "latitude": 19.07, "longitude": 72.87 },
  "departure_time": "2026-08-20T06:00:00Z"
}
```

- When `imo_number` is supplied, `ship` particulars are optional (backend uses the identified/default profile).
- `departure_time` is optional. If omitted, the backend automatically uses the current UTC time.

### Flow B: Without IMO Number (Custom Ship Particulars)

```json
{
  "imo_number": null,
  "start": { "latitude": 18.52, "longitude": 72.91 },
  "destination": { "latitude": 19.07, "longitude": 72.87 },
  "departure_time": "2026-08-20T06:00:00Z",
  "ship": {
    "ship_type": "Bulk Carrier",
    "length_m": 225.0,
    "beam_m": 32.2,
    "draft_m": 12.5,
    "cruising_speed_kn": 14.0,
    "max_speed_kn": 17.0
  }
}
```

- If `imo_number` is omitted or null, a complete `ship` object with all 6 fields is required.
- The backend customizes fuel, safety, and speed models using the supplied ship particulars.

---

## 7. Key Response Fields

### Route Preview Response (`POST /api/routes/preview`)

```json
{
  "imo_number": "1234567",
  "status": "route_ready",
  "departure_time": "2026-08-20T06:00:00Z",
  "eta": "2026-08-20T12:31:00Z",
  "route": [
    { "latitude": 18.52, "longitude": 72.91 },
    { "latitude": 18.65, "longitude": 72.95 },
    { "latitude": 18.82, "longitude": 72.92 },
    { "latitude": 19.07, "longitude": 72.87 }
  ],
  "distance_nm": 117.14,
  "estimated_time_hours": 6.51,
  "total_cost": 16.31
}
```

- **`departure_time`**: The effective UTC departure time used for environmental forecast sampling.
- **`eta`**: Calculated UTC arrival timestamp (`departure_time + estimated_time_hours`). Display directly in the UI without manual client-side duration math.
- **`route`**: Ordered waypoint coordinates to render as a polyline on the map.
- **`total_cost`**: Multi-objective environmental cost (dimensionless score; lower is better).

---

## 8. Error Handling

All error responses use the standard envelope:

```json
{
  "error": {
    "code": "INVALID_IMO",
    "message": "IMO number check digit is invalid (ISO 8713)."
  }
}
```

### Standard Error Codes & Statuses

| Code | HTTP Status | Meaning | Recommended UI Action |
|---|---|---|---|
| `INVALID_IMO` | `422` | IMO format or checksum failed | Highlight IMO input with error message |
| `INVALID_COORDINATES` | `422` | Latitude/Longitude out of range | Highlight coordinate input / map bounds |
| `SHIP_NOT_FOUND` | `404` | Ship IMO not recognized | Prompt user to input vessel particulars manually |
| `ROUTE_NOT_FOUND` | `404` | No navigable path between points | Inform user to choose alternative coordinates |
| `ENVIRONMENT_UNAVAILABLE` | `503` | Meteorological providers unreachable | Show "Environmental service degraded" warning |
| `TRACKING_UNAVAILABLE` | `503` | Live tracking service offline | Disable live tracking button with tooltip |
| `INTERNAL_ERROR` | `500` | Unexpected server failure | Display generic error notification banner |

---

## 9. WebSocket Integration

- **Path:** `/ws/ships/{imo_number}`
- **Handshake:** Open connection with valid 7-digit IMO. Invalid IMO is rejected with close code `1008` (Policy Violation).
- **Message Types:**
  - `route_update`: Contains new `route`, `distance_nm`, `estimated_time_hours`, `total_cost`, and `reason` (`"environment_changed"`, `"position_deviation"`, `"forecast_refresh"`).
  - `position_update`: Contains updated `position` and `timestamp`.
- **Reconnect Handling:** On disconnection, reconnect and call `GET /api/ships/{imo}/status` and `GET /api/ships/{imo}/route` to synchronize UI state.

---

## 10. MVP Scope & Limitations

The following features were intentionally excluded or deferred from MVP Contract v2:

- **Hazard/Alerts Array:** Alerts are not part of the MVP payload; use the `reason` string on `route_update`.
- **Per-Leg Details (`legs`):** Segment-by-segment weather breakdowns are deferred to post-MVP.
- **Baseline Cost (`baseline_cost`):** Comparison against naive direct route is deferred to post-MVP.
- **External AIS / Registry:** Ship lookup returns demo vessel defaults; manual ship particular entry is supported.
- **Land Masking & Bathymetry:** Landmass avoidance is constrained to sea corridors during demo mode.

---

## 11. Summary

For complete schema definitions, type structures, and field constraints, refer directly to [`docs/API_CONTRACT.md`](./API_CONTRACT.md).
