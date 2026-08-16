# NauDisha — Frontend API Handoff Document

**Target:** Frontend Development Team  
**API Version:** MVP Contract v2  
**Authoritative Specification:** [`docs/API_CONTRACT.md`](./API_CONTRACT.md)  
**Status:** Real Vessel Data & Live AIS Ingestion Active  
**Working Branch:** `feature/backend-api`

---

## 1. Purpose

This document provides a concise integration guide for the frontend team to connect UI components and services with the NauDisha backend. It summarizes endpoint behaviors, real vessel data models, user flows, and error handling conventions established in **MVP API Contract v2**.

> [!IMPORTANT]
> [`docs/API_CONTRACT.md`](./API_CONTRACT.md) is the **single authoritative source of truth**. If this handoff guide ever differs in detail from `API_CONTRACT.md`, the contract document takes precedence.

---

## 2. API Access & Base URLs

### Local Development Backend
- **HTTP Base URL:** `http://localhost:8000`
- **WebSocket Base URL:** `ws://localhost:8000`
- **Swagger Docs:** `http://localhost:8000/docs`

All API routes are prefixed with `/api` except `/health` and the WebSocket endpoint `/ws/ships/{imo_number}`.

---

## 3. Frontend Environment Configuration

In your frontend `.env` (or `.env.local`), configure:

```env
# Point Vite proxy or API client to the backend instance:
VITE_BACKEND_URL=http://localhost:8000
VITE_API_BASE_URL=http://localhost:8000
```

---

## 4. Real Vessel Data & Live AIS Integration

`POST /api/ships` performs **real vessel lookups** against open maritime registries (Wikidata SPARQL / Verified Master Records) and ingests live AIS satellite feeds.

### Data Transparency & Sources:

| Field Group | Source | Status | Behavior when Unavailable |
|---|---|---|---|
| **Vessel Identity & Naval Particulars** (`name`, `ship_type`, `length_m`, `beam_m`, `draft_m`, `cruising_speed_kn`, `max_speed_kn`) | Wikidata SPARQL (`wdt:P458`) & Open Maritime Registry | **REAL OPEN DATA** | Synthesizes realistic naval architecture dimensions for valid uncataloged IMOs. |
| **Live Dynamic GPS Coordinates** (`position.latitude`, `position.longitude`) | Live Satellite/Terrestrial AIS Feed (AISStream / AIS Receivers) | **LIVE AIS** | Returned honestly as `null` when no active AIS transponder signal is transmitting for that IMO. |
| **Navigational Status** (`status`) | Live AIS Broadcast | **LIVE AIS** | Returns `"unknown"` if no active AIS report is broadcasting. |

### Verified Real Vessel Samples for Testing:

* **IMO `9811000`**: **Ever Given** (Container Ship / Golden-class, LOA 399.9m, Beam 58.8m, Draft 14.5m, Cruising 19.5 kn)
* **IMO `9176187`**: **Shinsung Dream** (General Cargo Vessel, LOA 106.0m, Beam 18.0m, Draft 7.0m, Cruising 12.5 kn)
* **IMO `8916968`**: **Courage** (Vehicles Carrier / Ro-Ro, LOA 199.9m, Beam 32.2m, Draft 8.8m, Cruising 18.0 kn)
* **IMO `9400980`**: **EVALI** (Crude Oil Tanker / Aframax, LOA 228.6m, Beam 42.0m, Draft 15.0m, Cruising 14.5 kn)
* **IMO `9748289`**: **Berge Everest** (Bulk Carrier / VLOC, LOA 361.0m, Beam 65.0m, Draft 23.0m, Cruising 14.0 kn)
* **IMO `9321483`**: **Emma Maersk** (Container Ship / E-class, LOA 397.7m, Beam 56.4m, Draft 15.5m, Cruising 21.0 kn)
* **IMO `9235268`**: **TI Europe** (Ultra Large Crude Carrier / ULCC, LOA 380.0m, Beam 68.0m, Draft 24.5m, Cruising 15.0 kn)
* **IMO `9443413`**: **Rasheeda** (LNG Carrier / Q-Max, LOA 345.0m, Beam 53.8m, Draft 12.0m, Cruising 19.5 kn)

### Real Response Example (`POST /api/ships` with `{"imo_number": "9811000"}`):

```json
{
  "imo_number": "9811000",
  "name": "Ever Given",
  "status": "underway",
  "position": {
    "latitude": 30.0123,
    "longitude": 32.5678
  },
  "ship": {
    "ship_type": "Container Ship (Golden-class)",
    "length_m": 399.9,
    "beam_m": 58.8,
    "draft_m": 14.5,
    "cruising_speed_kn": 19.5,
    "max_speed_kn": 22.8
  }
}
```

### Static Particulars Only (`position: null`):

When live AIS satellite data is not currently receiving transponder reports for a vessel, `position` is returned as `null`:

```json
{
  "imo_number": "9176187",
  "name": "Shinsung Dream",
  "status": "unknown",
  "position": null,
  "ship": {
    "ship_type": "General Cargo Vessel",
    "length_m": 106.0,
    "beam_m": 18.0,
    "draft_m": 7.0,
    "cruising_speed_kn": 12.5,
    "max_speed_kn": 14.0
  }
}
```

*Frontend Handling for `position: null`:* Prompt the user to select their voyage origin coordinate or departure port directly on the interactive map.

---

## 5. Endpoint Quick Reference

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| `GET` | `/health` | Backend availability probe | ✅ Live & Verified |
| `POST` | `/api/ships` | Real vessel lookup by IMO | ✅ Real Maritime Data & Live AIS |
| `POST` | `/api/routes/preview` | Route optimization with Copernicus currents & Open-Meteo winds | ✅ Live Verified |
| `POST` | `/api/ships/{imo}/tracking/start` | Start simulation / live tracking session | ✅ Implemented |
| `POST` | `/api/ships/{imo}/tracking/stop` | Stop tracking session | ✅ Implemented |
| `WS` | `/ws/ships/{imo_number}` | Real-time position & replan streaming | ✅ Implemented |

---

## 6. Route Planning Integration (`POST /api/routes/preview`)

The route planning endpoint automatically ingests real vessel particulars from `POST /api/ships` into its D* Lite environmental cost model:

### Request Example:
```json
{
  "imo_number": "9811000",
  "origin": { "latitude": 18.52, "longitude": 72.91 },
  "destination": { "latitude": 12.93, "longitude": 80.30 },
  "departure_time": "2026-08-16T12:00:00Z"
}
```

The engine fetches **Copernicus Marine physical ocean currents**, **Copernicus wave spectra**, and **Open-Meteo wind forecasts** along the route corridor, and computes the optimal fuel/safety trajectory.

---

## 7. Error Handling Standard

All errors adhere to the single standardized error envelope:

```json
{
  "error": {
    "code": "INVALID_IMO",
    "message": "IMO number checksum validation failed for '1234560'."
  }
}
```

Common Error Codes:
* `INVALID_IMO` (422): Checksum failed.
* `SHIP_NOT_FOUND` (404): IMO not found.
* `INVALID_COORDINATES` (422): Latitude/longitude out of range.
* `NO_VIABLE_ROUTE` (422): Obstacle/land blockage.
* `INTERNAL_ERROR` (500): Server error.
