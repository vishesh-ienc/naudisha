# NauDisha — MVP API Contract v2

**Version:** 2.0
**Status:** Final — single source of truth for frontend and backend.
**Supersedes:** API Contract v1, API Contract Addendum Proposal.

Both frontend and backend MUST follow this document.

The frontend must never assume or invent fields that are not defined here.

The backend must return the structures defined here.

---

## §1 Base URL

Development:

```
http://localhost:8000
```

All HTTP endpoints below are relative to this base URL.

WebSocket endpoint uses `ws://` on the same host and port.

---

## §2 Data Conventions

### §2.1 Coordinates

All geographic coordinates use the `Coordinate` object:

```json
{
  "latitude": 18.52,
  "longitude": 72.91
}
```

| Field | Type | Range | Required |
|---|---|---|---|
| `latitude` | `number` | −90.0 to +90.0 | Yes |
| `longitude` | `number` | −180.0 to +180.0 | Yes |

### §2.2 Timestamps

All timestamps are ISO 8601 UTC strings with `Z` suffix.

```
"2026-08-20T06:00:00Z"
```

### §2.3 IMO Number

IMO numbers are represented as **strings of exactly 7 digits**.

```
"1234567"
```

Do NOT represent IMO numbers as integers.

**Validation rule (ISO 8713):**

Both frontend and backend apply the same rule:

1. The string must match `^\d{7}$` (exactly 7 digits).
2. The 7th digit is a check digit: multiply the first six digits by weights `[7, 6, 5, 4, 3, 2]`, sum the products, and the last digit of the sum must equal the 7th digit.

Example:

```
IMO 1234567:
  1×7 + 2×6 + 3×5 + 4×4 + 5×3 + 6×2 = 77
  77 mod 10 = 7 → matches 7th digit ✓
```

### §2.4 Ship Profile

Ship characteristics are represented as a `ShipProfile` object with explicit unit suffixes:

```json
{
  "ship_type": "Container Vessel (Panamax)",
  "length_m": 294.0,
  "beam_m": 32.2,
  "draft_m": 12.0,
  "cruising_speed_kn": 18.0,
  "max_speed_kn": 23.0
}
```

| Field | Type | Unit | Description |
|---|---|---|---|
| `ship_type` | `string` | — | Vessel classification |
| `length_m` | `number` | metres | Overall length (LOA), must be > 0 |
| `beam_m` | `number` | metres | Width at widest point, must be > 0 |
| `draft_m` | `number` | metres | Maximum submerged depth, must be > 0 |
| `cruising_speed_kn` | `number` | knots | Design service speed, must be > 0 |
| `max_speed_kn` | `number` | knots | Maximum operational speed, must be ≥ `cruising_speed_kn` |

When present, **all six fields are required** (no partial objects).

### §2.5 Error Format

All API errors use a consistent envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description."
  }
}
```

| Field | Type | Description |
|---|---|---|
| `code` | `string` | Machine-readable error code from §15 |
| `message` | `string` | Human-readable description for display or logging |

---

## §3 GET /health

Backend availability check.

**Purpose:** Frontend uses this to detect whether the backend is reachable before making API calls.

### Request

```
GET /health
```

No request body.

### Response — 200 OK

```json
{
  "status": "ok",
  "service": "naudisha-backend"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | Always `"ok"` when backend is reachable |
| `service` | `string` | Always `"naudisha-backend"` |

This endpoint does not query external data providers or routing engines.

---

## §4 POST /api/ships

Identify a vessel by IMO number.

**Purpose:** Used when the user enters an IMO number to look up a ship. For the MVP, this returns a demo vessel with default characteristics. The frontend should display the returned ship profile and indicate whether it represents looked-up data or defaults.

### Request

```json
{
  "imo_number": "1234567"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `imo_number` | `string` | Yes | Valid 7-digit IMO number (§2.3) |

### Response — 200 OK

```json
{
  "imo_number": "1234567",
  "name": "Demo Vessel",
  "status": "underway",
  "position": {
    "latitude": 18.52,
    "longitude": 72.91
  },
  "ship": {
    "ship_type": "Container Vessel (Panamax)",
    "length_m": 294.0,
    "beam_m": 32.2,
    "draft_m": 12.0,
    "cruising_speed_kn": 18.0,
    "max_speed_kn": 23.0
  }
}
```

| Field | Type | Description |
|---|---|---|
| `imo_number` | `string` | Echoed IMO number |
| `name` | `string` | Vessel name |
| `status` | `string` | Ship status (see §13.1) |
| `position` | `Coordinate` | Current or last-known position |
| `ship` | `ShipProfile` | Vessel characteristics (§2.4) used for routing |

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | IMO number fails §2.3 validation |
| `SHIP_NOT_FOUND` | 404 | IMO not recognized by lookup service |

---

## §5 POST /api/routes/preview

Calculate an optimal route between two coordinates.

**Purpose:** Used in Flow B ("Plan a Voyage") to compute and display an environment-aware optimal route. The backend samples real-time oceanographic and atmospheric forecast data for the specified departure time, constructs a navigation grid, and runs D* Lite to find the least-cost path.

### Request

```json
{
  "imo_number": "1234567",
  "start": {
    "latitude": 18.52,
    "longitude": 72.91
  },
  "destination": {
    "latitude": 19.07,
    "longitude": 72.87
  },
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

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `imo_number` | `string` or `null` | No | `null` | Valid 7-digit IMO (§2.3). May be omitted or `null` for IMO-less routing. |
| `start` | `Coordinate` | Yes | — | Departure coordinates |
| `destination` | `Coordinate` | Yes | — | Arrival coordinates |
| `departure_time` | `string` or `null` | No | Current UTC time | ISO 8601 UTC timestamp for environmental forecast sampling |
| `ship` | `ShipProfile` or `null` | No | Backend default profile | Vessel characteristics to use for cost calculation (§2.4) |

**Validation rules:**

- `start` and `destination` are required.
- At least one of `imo_number` or `ship` may be provided, or both may be omitted (backend uses default ship profile).
- When `imo_number` is provided, it must pass §2.3 validation.
- When `ship` is provided, all six fields of `ShipProfile` (§2.4) are required.
- When `departure_time` is omitted or `null`, the backend defaults to the current UTC time.

### Response — 200 OK

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

| Field | Type | Nullable | Description |
|---|---|---|---|
| `imo_number` | `string` or `null` | Yes | Echoed IMO, or `null` if IMO-less routing was used |
| `status` | `string` | No | Always `"route_ready"` on success |
| `departure_time` | `string` | No | The departure time actually used for environmental sampling (ISO 8601 UTC) |
| `eta` | `string` | No | Estimated time of arrival: `departure_time` + `estimated_time_hours` (ISO 8601 UTC) |
| `route` | `Coordinate[]` | No | Ordered list of waypoints from start to destination |
| `distance_nm` | `number` | No | Total route distance in nautical miles |
| `estimated_time_hours` | `number` | No | Estimated transit duration in hours |
| `total_cost` | `number` | No | Multi-objective environmental route cost (dimensionless weighted sum; lower is better; `0.0` when start equals destination) |

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | `imo_number` was provided and fails §2.3 validation |
| `INVALID_COORDINATES` | 422 | `start` or `destination` coordinates out of bounds |
| `ROUTE_NOT_FOUND` | 404 | No navigable route exists between the coordinates |
| `ENVIRONMENT_UNAVAILABLE` | 503 | Environmental data providers (Copernicus Marine, Open-Meteo) failed |
| `INTERNAL_ERROR` | 500 | Unexpected backend failure |

---

## §6 POST /api/ships/{imo_number}/tracking/start

Begin live tracking for a vessel.

**Purpose:** Initiates live position tracking and dynamic route replanning for the specified ship. Typically called after the user previews a route (§5) and clicks "Start Tracking".

### Request

```
POST /api/ships/1234567/tracking/start
```

```json
{
  "destination": {
    "latitude": 19.07,
    "longitude": 72.87
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `destination` | `Coordinate` | Yes | Voyage destination for route planning and replanning |
| `origin` | `Coordinate` or `null` | No | Starting position. Falls back to the vessel's live AIS position, then to a default open-water origin when no AIS fix is available. |
| `departure_time` | `string` or `null` | No | ISO 8601 UTC timestamp used for environmental forecast sampling |

### Response — 200 OK

```json
{
  "imo_number": "1234567",
  "tracking": true,
  "message": "Ship tracking started"
}
```

| Field | Type | Description |
|---|---|---|
| `imo_number` | `string` | IMO number from the URL path |
| `tracking` | `boolean` | Always `true` on success |
| `message` | `string` | Human-readable confirmation |

**This call returns immediately.** Route computation samples live Copernicus
Marine data and takes up to ~2 minutes from cold, so it runs in the background.
Until it completes, `GET /api/ships/{imo}/route` reports
`route_status: "updating"` with an empty `route` array. When the plan lands, a
`route_update` message is pushed to any connected WebSocket client (§10).

Clients must not treat `"updating"` as an error, and must not block the UI
waiting for the first route.

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | IMO in URL path fails §2.3 validation |
| `INVALID_COORDINATES` | 422 | `destination` coordinates out of bounds, or equal to the origin |
| `SHIP_NOT_FOUND` | 404 | IMO not recognized |
| `TRACKING_UNAVAILABLE` | 503 | Tracking service is not available |

---

## §6.1 POST /api/ships/{imo_number}/tracking/stop

End an active tracking session.

### Request

```
POST /api/ships/1234567/tracking/stop
```

No request body.

### Response — 200 OK

```json
{
  "imo_number": "1234567",
  "tracking": false,
  "message": "Ship tracking stopped"
}
```

Idempotent: stopping a vessel that is not being tracked returns 200 with
`message: "No active tracking session"`.

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | IMO in URL path fails §2.3 validation |

---

## §7 GET /api/ships/{imo_number}/status

Get current ship status and position.

**Purpose:** Used by the frontend to poll ship state, particularly after a WebSocket reconnect or as a fallback when WebSocket is unavailable.

### Request

```
GET /api/ships/1234567/status
```

No request body.

### Response — 200 OK

```json
{
  "imo_number": "1234567",
  "status": "underway",
  "position": {
    "latitude": 18.58,
    "longitude": 72.94
  },
  "destination": {
    "latitude": 19.07,
    "longitude": 72.87
  },
  "timestamp": "2026-08-16T06:30:00Z"
}
```

| Field | Type | Nullable | Description |
|---|---|---|---|
| `imo_number` | `string` | No | IMO number |
| `status` | `string` | No | Ship status (see §13.1) |
| `position` | `Coordinate` | No | Current or last-known position |
| `destination` | `Coordinate` or `null` | Yes | Active voyage destination, or `null` if no voyage is in progress |
| `timestamp` | `string` | No | Time of the position observation (ISO 8601 UTC) |

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | IMO fails §2.3 validation |
| `SHIP_NOT_FOUND` | 404 | IMO not recognized |

---

## §8 GET /api/ships/{imo_number}/route

Get the current optimal route for a tracked ship.

**Purpose:** Returns the most recently computed optimal route for the ship. The route may have been updated by dynamic replanning since the initial preview.

### Request

```
GET /api/ships/1234567/route
```

No request body.

### Response — 200 OK

```json
{
  "imo_number": "1234567",
  "route_status": "optimal",
  "destination": {
    "latitude": 19.07,
    "longitude": 72.87
  },
  "route": [
    { "latitude": 18.58, "longitude": 72.94 },
    { "latitude": 18.75, "longitude": 72.91 },
    { "latitude": 19.07, "longitude": 72.87 }
  ],
  "distance_nm": 110.42,
  "estimated_time_hours": 6.12,
  "total_cost": 15.87,
  "updated_at": "2026-08-16T06:30:00Z"
}
```

| Field | Type | Nullable | Description |
|---|---|---|---|
| `imo_number` | `string` | No | IMO number |
| `route_status` | `string` | No | Route status (see §13.2) |
| `destination` | `Coordinate` or `null` | Yes | Active voyage destination |
| `route` | `Coordinate[]` | No | Ordered waypoints, starting from current position to destination |
| `distance_nm` | `number` | No | Remaining route distance in nautical miles |
| `estimated_time_hours` | `number` | No | Estimated remaining transit time in hours |
| `total_cost` | `number` | No | Current total route cost |
| `updated_at` | `string` | No | When this route was last computed (ISO 8601 UTC) |

### Errors

| Code | HTTP | When |
|---|---|---|
| `INVALID_IMO` | 422 | IMO fails §2.3 validation |
| `SHIP_NOT_FOUND` | 404 | IMO not recognized |
| `ROUTE_NOT_FOUND` | 404 | No route currently exists for the ship |

---

## §9 WebSocket /ws/ships/{imo_number}

Live ship position and route updates.

**Purpose:** Provides real-time push updates for ship position changes and route recalculations during active tracking.

### Connection

```
ws://localhost:8000/ws/ships/1234567
```

- The client opens the WebSocket connection. No authentication or subscribe message is required.
- The server begins pushing messages immediately after the connection is established.
- Standard WebSocket ping/pong frames are used for connection liveness detection. No application-level heartbeat protocol.

### Message Format

All messages are JSON objects with a `type` field that determines the message structure.

Two message types are defined:

| Type | Description | Defined in |
|---|---|---|
| `"route_update"` | New route computed due to environmental change or replanning | §10 |
| `"position_update"` | Ship position changed without route recalculation | §11 |

### Ordering

Messages carry a `timestamp` field. Messages are sent in chronological order. The frontend should use `timestamp` to discard any out-of-order messages received due to network delays.

### Disconnect Behavior

- The client may reconnect at any time after a disconnect.
- The server does not persist WebSocket session state across disconnections.
- After reconnecting, the frontend should call `GET /api/ships/{imo}/status` (§7) and `GET /api/ships/{imo}/route` (§8) to restore current state.

### Update Cadence (MVP Demo)

- Position updates are sent approximately every 30 seconds (simulated for demo).
- Route re-evaluation occurs when environmental conditions change, resulting in a `route_update` message.

---

## §10 WebSocket Message: route_update

Sent when the backend has recalculated the optimal route.

```json
{
  "type": "route_update",
  "timestamp": "2026-08-16T06:35:00Z",
  "position": {
    "latitude": 18.61,
    "longitude": 72.95
  },
  "route": [
    { "latitude": 18.61, "longitude": 72.95 },
    { "latitude": 18.82, "longitude": 72.88 },
    { "latitude": 19.07, "longitude": 72.87 }
  ],
  "distance_nm": 108.32,
  "estimated_time_hours": 6.01,
  "total_cost": 15.42,
  "reason": "environment_changed"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | `string` | Always `"route_update"` |
| `timestamp` | `string` | Time of the recalculation (ISO 8601 UTC) |
| `position` | `Coordinate` | Current ship position at time of update |
| `route` | `Coordinate[]` | Updated waypoints from current position to destination |
| `distance_nm` | `number` | Updated remaining distance in nautical miles |
| `estimated_time_hours` | `number` | Updated remaining transit time in hours |
| `total_cost` | `number` | Updated total route cost |
| `reason` | `string` | Why the route was recalculated (see §13.3) |

---

## §11 WebSocket Message: position_update

Sent when the ship's position has changed without a route recalculation.

```json
{
  "type": "position_update",
  "timestamp": "2026-08-16T06:40:00Z",
  "position": {
    "latitude": 18.65,
    "longitude": 72.96
  }
}
```

| Field | Type | Description |
|---|---|---|
| `type` | `string` | Always `"position_update"` |
| `timestamp` | `string` | Time of the position observation (ISO 8601 UTC) |
| `position` | `Coordinate` | Current ship position |

---

## §12 Reserved

This section is intentionally left empty to preserve numbering alignment.

---

## §13 Enumerations

### §13.1 Ship Status

Used in `POST /api/ships` response and `GET /api/ships/{imo}/status` response.

| Value | Meaning |
|---|---|
| `"underway"` | Ship is actively sailing |
| `"stopped"` | Ship is stationary |
| `"unknown"` | Status cannot be determined |

### §13.2 Route Status

Used in `GET /api/ships/{imo}/route` response.

| Value | Meaning |
|---|---|
| `"optimal"` | Route is the current optimal path |
| `"updating"` | Route is being recalculated |
| `"unavailable"` | No valid route could be computed |

### §13.3 Route Update Reason

Used in the `reason` field of `route_update` WebSocket messages.

| Value | Meaning |
|---|---|
| `"environment_changed"` | Oceanographic or atmospheric conditions changed |
| `"position_deviation"` | Ship deviated from the planned route |
| `"forecast_refresh"` | Forecast data was refreshed with newer observations |

The frontend should display the reason as-is if the value is not recognized. Unknown reason values must not cause a frontend error.

---

## §14 Error Format

All API errors use the structure defined in §2.5:

```json
{
  "error": {
    "code": "SHIP_NOT_FOUND",
    "message": "No ship found for the provided IMO number."
  }
}
```

The `code` field is machine-readable. The `message` field is for display or logging.

---

## §15 Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| `INVALID_IMO` | 422 | The supplied IMO number fails validation (§2.3) |
| `SHIP_NOT_FOUND` | 404 | The requested ship could not be found |
| `INVALID_COORDINATES` | 422 | Start or destination coordinates are out of valid range |
| `ROUTE_NOT_FOUND` | 404 | No navigable route could be calculated between the specified coordinates |
| `TRACKING_UNAVAILABLE` | 503 | Live tracking service is currently unavailable |
| `ENVIRONMENT_UNAVAILABLE` | 503 | Environmental data providers could not be reached |
| `INTERNAL_ERROR` | 500 | Unexpected backend error (no internal details are exposed to the client) |

---

## §16 Frontend / Backend Responsibilities

### Frontend

Responsible for:

- Collecting user input (IMO number, coordinates, departure time, ship details)
- Validating basic input format (IMO check digit, coordinate ranges)
- Calling backend APIs
- Displaying ship information, routes, and route statistics
- Displaying tracking state and live updates
- Handling loading and error states
- Rendering map with ship markers, route polylines, and destination markers

### Backend

Responsible for:

- Authoritative data validation
- Ship lookup and tracking state management
- Fetching environmental data (ocean currents, waves, wind)
- Route computation via D* Lite
- Multi-factor cost calculation
- Dynamic replanning on environmental changes
- API error semantics and HTTP status codes

### Strict Prohibitions

The frontend MUST NEVER:

- Call Copernicus Marine Service directly
- Call Open-Meteo directly
- Implement D* Lite or any routing algorithm
- Calculate route costs or environmental scores
- Invent route data not received from the backend

The backend is the single source of truth for all routing, scoring, and environmental data.

---

## §17 MVP Endpoint Summary

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/health` | Backend availability check | Implemented |
| `POST` | `/api/ships` | Identify vessel by IMO | Implemented (real vessel data + live AIS) |
| `POST` | `/api/routes/preview` | Calculate optimal route | Implemented |
| `POST` | `/api/ships/{imo}/tracking/start` | Begin live tracking | Implemented |
| `POST` | `/api/ships/{imo}/tracking/stop` | End live tracking | Implemented |
| `GET` | `/api/ships/{imo}/status` | Current ship status | Implemented |
| `GET` | `/api/ships/{imo}/route` | Current optimal route | Implemented |
| `WS` | `/ws/ships/{imo}` | Live position and route updates | Implemented |

All endpoints are live. `/status` and `/route` are backed by real tracking
sessions rather than fixed responses, and the WebSocket streams genuine
`position_update` and `route_update` messages from the navigation simulator.

**Known limitations, so clients build around them rather than into them:**

- `POST /api/ships` returns `position: null` when no live AIS report is
  available for that vessel, which is the common case without an
  `AISSTREAM_API_KEY`. Clients must handle a null position — typically by asking
  the user to choose a starting point.
- A cold `POST /api/routes/preview` can take ~2 minutes while Copernicus Marine
  is queried; repeat requests for the same corridor and hour are served from
  cache in under a second. Set client timeouts accordingly.
- Vessel movement during tracking is simulated dead reckoning along the planned
  route, not an AIS observation feed. Interfaces should say so.
- The routing grid is 4-connected (N/S/E/W), so routes contain right-angle
  steps. Clients may smooth the polyline for display but must not alter the
  reported waypoints or distances.

Additional endpoints should only be added when a real MVP requirement demands them.
