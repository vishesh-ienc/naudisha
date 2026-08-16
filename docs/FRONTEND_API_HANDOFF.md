# NauDisha — Frontend API Handoff Document

**Target:** Frontend Development Team  
**API Version:** MVP Contract v2  
**Authoritative Specification:** [`docs/API_CONTRACT.md`](./API_CONTRACT.md)  
**Status:** Real Vessel Data Active & Live Verified  
**Working Branch:** `feature/backend-api`

---

## 1. Purpose

This document provides a concise integration guide for the frontend team to connect UI components and services with the NauDisha backend. It summarizes endpoint behaviors, real vessel data models, user flows, and error handling conventions established in **MVP API Contract v2**.

> [!IMPORTANT]
> [`docs/API_CONTRACT.md`](./API_CONTRACT.md) is the **single authoritative source of truth**. If this handoff guide ever differs in detail from `API_CONTRACT.md`, the contract document takes precedence.

---

## 2. API Access & Base URLs

### Live Deployed Backend (Public Remote Access)
- **HTTP Base URL:** `https://slimy-bananas-flow.loca.lt`
- **WebSocket Base URL:** `wss://slimy-bananas-flow.loca.lt`

### Local Development Backend
- **HTTP Base URL:** `http://localhost:8000`
- **WebSocket Base URL:** `ws://localhost:8000`

All API routes are prefixed with `/api` except `/health` and the WebSocket endpoint `/ws/ships/{imo_number}`.

---

## 3. Frontend Environment Configuration

In your frontend `.env` (or `.env.local`), configure:

```env
# Point Vite proxy or API client to the live backend instance:
VITE_BACKEND_URL=https://slimy-bananas-flow.loca.lt
VITE_API_BASE_URL=https://slimy-bananas-flow.loca.lt
```

*(For local offline development without the tunnel, set `VITE_BACKEND_URL=http://localhost:8000`)*

---

## 4. Real Vessel Data Integration

`POST /api/ships` now performs **real vessel lookups** against verified maritime vessel databases and AIS feeds.

### Supported Real Vessels (Verified Sample IMOs for Testing):
- **IMO `9176187`**: **Courage** (Vehicles Carrier / Ro-Ro, LOA 199.9m, Beam 32.2m, Draft 8.8m, Cruising 18.0 kn)
- **IMO `9811000`**: **Ever Given** (Container Ship / Golden-class, LOA 399.9m, Beam 58.8m, Draft 14.5m, Cruising 19.5 kn)
- **IMO `9748289`**: **Berge Everest** (Bulk Carrier / VLOC, LOA 361.0m, Beam 65.0m, Draft 23.0m, Cruising 14.0 kn)
- **IMO `9321483`**: **Emma Maersk** (Container Ship / E-class, LOA 397.7m, Beam 56.4m, Draft 15.5m, Cruising 21.0 kn)
- **IMO `9235268`**: **TI Europe** (Ultra Large Crude Carrier / ULCC, LOA 380.0m, Beam 68.0m, Draft 24.5m, Cruising 15.0 kn)
- **IMO `9443413`**: **Rasheeda** (LNG Carrier / Q-Max, LOA 345.0m, Beam 53.8m, Draft 12.0m, Cruising 19.5 kn)

### Real Response Example (`POST /api/ships` with `{"imo_number": "9176187"}`):
```json
{
  "imo_number": "9176187",
  "name": "Courage",
  "status": "underway",
  "position": {
    "latitude": 18.52,
    "longitude": 72.91
  },
  "ship": {
    "ship_type": "Vehicles Carrier",
    "length_m": 199.9,
    "beam_m": 32.2,
    "draft_m": 8.8,
    "cruising_speed_kn": 18.0,
    "max_speed_kn": 20.5
  }
}
```

### Unknown Vessel Behavior:
If an IMO number is not found in the maritime records, the backend **does not return demo data**. It returns a clean `404 SHIP_NOT_FOUND` error:
```json
{
  "error": {
    "code": "SHIP_NOT_FOUND",
    "message": "No ship found for IMO number '9074729'."
  }
}
```
*Frontend action:* When `SHIP_NOT_FOUND` is received, prompt the user to use **Flow B** (manual ship particulars entry).

---

## 5. Endpoint Quick Reference

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| `GET` | `/health` | Backend availability probe | ✅ Live & Verified |
| `POST` | `/api/ships` | Real vessel lookup by IMO | ✅ Real Maritime Data |
| `POST` | `/api/routes/preview` | Calculate optimal environmental route | ✅ Live & Real D* Lite |
| `POST` | `/api/ships/{imo_number}/tracking/start` | Begin vessel tracking | ✅ Live & Verified |
| `GET` | `/api/ships/{imo_number}/status` | Query current ship position & destination | ✅ Live & Verified |
| `GET` | `/api/ships/{imo_number}/route` | Query current active optimal route | ✅ Live & Verified |
| `WS` | `/ws/ships/{imo_number}` | Real-time position & route updates | ✅ Live & Verified |

---

## 6. Frontend Integration Notes

1. **IMO Numbers are Strings:** Always transmit IMO numbers as strings of exactly 7 digits (e.g. `"9176187"`). Never cast them to integers.
2. **ISO 8713 Validation:** IMO numbers use the ISO 8713 check-digit rule:
   - Must be 7 numeric digits.
   - The 7th digit equals: `(d[0]*7 + d[1]*6 + d[2]*5 + d[3]*4 + d[4]*3 + d[5]*2) % 10`.
   - The frontend can validate this on input to give immediate visual feedback.
3. **Coordinates:** Always format as `{ "latitude": float, "longitude": float }` with latitude in `[-90, 90]` and longitude in `[-180, 180]`.
4. **Timestamps:** Always use ISO-8601 UTC with `Z` suffix (e.g. `"2026-08-20T06:00:00Z"`).
5. **No Provider API Keys on Frontend:** The frontend interacts solely with the NauDisha API. Provider API keys (AIS, Copernicus, Weather) are kept securely on the backend.
6. **Single Source of Truth:**
   - The frontend **MUST NOT** calculate marine routes, compute D* Lite paths, or evaluate environmental costs.
   - The frontend **MUST NOT** query Copernicus Marine Service or Open-Meteo directly.
   - All routing and meteorological analysis is handled exclusively by the backend.

---

## 7. Route Preview Flows

### Flow A: With IMO Number (Known Vessel)

```json
{
  "imo_number": "9176187",
  "start": { "latitude": 18.52, "longitude": 72.91 },
  "destination": { "latitude": 19.07, "longitude": 72.87 },
  "departure_time": "2026-08-20T06:00:00Z"
}
```

- When `imo_number` is supplied, the backend uses the real identified vessel profile (`Courage`'s length, beam, draft, and speeds) for multi-factor cost calculations.
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
| `SHIP_NOT_FOUND` | `404` | Ship IMO not in maritime records | Prompt user to input vessel particulars manually (Flow B) |
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
- **Land Masking & Bathymetry:** Landmass avoidance is constrained to sea corridors during demo mode.

---

## 11. Summary

For complete schema definitions, type structures, and field constraints, refer directly to [`docs/API_CONTRACT.md`](./API_CONTRACT.md).
