# Current Prompt: Phase 8.4 — Implement Final MVP API Contract v2 + Push Contract to Main

## Goal

Align the backend implementation with the finalized MVP API Contract v2 (`docs/API_CONTRACT.md`), verify via full test suite, commit to `feature/backend-api`, push, and safely merge/push to `main`.

---

## 1. Branch

- **Working Branch**: `feature/backend-api`
- **Target Integration Branch**: `main`

---

## 2. Work Performed

### 1. ISO 8713 IMO Validation
- Implemented `validate_iso_8713_imo` in `naudisha/api/schemas.py`:
  - Enforces exactly 7 numeric digits (`^\d{7}$`).
  - Calculates checksum with weights `[7, 6, 5, 4, 3, 2]` modulo 10 and checks against the 7th digit.
  - Applied across `RoutePreviewRequest`, `ShipIdentifyRequest`, and path parameters on `/api/ships/{imo_number}/*`.

### 2. Ship Profile / Particulars Mapping
- Created `ShipProfileSchema` in `naudisha/api/schemas.py` with explicit unit suffixes (`length_m`, `beam_m`, `draft_m`, `cruising_speed_kn`, `max_speed_kn`).
- Added bidirectional conversion methods: `to_domain_model()` and `from_domain_model()`.
- Added `DEFAULT_SHIP_PROFILE_SCHEMA` for demo/MVP fallback.
- Updated `POST /api/ships` response to include the `ship: ShipProfileSchema` block (§4).

### 3. Route Preview Contract v2 Alignment
- Updated `RoutePreviewRequest`:
  - `imo_number: Optional[str] = None`
  - `departure_time: Optional[str] = None`
  - `ship: Optional[ShipProfileSchema] = None`
  - Validates that at least one of `imo_number` or `ship` is supplied.
- Updated `RoutePlanningService.plan_preview_route`:
  - Accepts `ship_profile: Optional[ShipProfile]` and uses it across the grid graph, environment population, and edge transit calculations.
  - Supports ISO-8601 UTC `departure_time` (defaults to actual current UTC time instead of hardcoding 12:00 UTC).
  - Computes `eta` (`departure_time + estimated_time_hours`) as ISO-8601 UTC timestamp.
- Updated `RoutePreviewResponse` with `departure_time` and `eta`.

### 4. Tracking, Status, and Route Endpoints
- Implemented `TrackingStartRequest` (`destination: Coordinate`) and `TrackingStartResponse` on `POST /api/ships/{imo_number}/tracking/start`.
- Updated `GET /api/ships/{imo_number}/status` to return `ShipStatusResponse` with `destination: Optional[Coordinate]`.
- Updated `GET /api/ships/{imo_number}/route` to return `ShipRouteResponse` with `destination: Optional[Coordinate]`.
- Added `ws_router` with WebSocket endpoint `/ws/ships/{imo_number}` in `naudisha/api/main.py`.

### 5. Error Status Code Alignment
- Updated `errors.py` so `InvalidIMOError` and `InvalidCoordinatesError` return HTTP 422 according to contract v2 §15.

### 6. Tests Verification
- Expanded `tests/test_api.py` to 27 test cases covering all 16 minimum test requirements.
- Full test suite: 149 tests passing with 0 failures and 0 errors.

---

## 3. Files Modified

| File | Changes |
|---|---|
| `naudisha/api/schemas.py` | Added ISO 8713 validation, ShipProfileSchema, tracking schemas, updated route preview & ship identify models |
| `naudisha/api/services.py` | Added `departure_time`, `eta` calculation, custom `ship_profile` injection, current UTC fallback |
| `naudisha/api/routes.py` | Wired departure_time & ship particulars to service; implemented tracking start, status, route, and ws endpoints |
| `naudisha/api/errors.py` | Aligned error status codes with API Contract v2 (HTTP 422 for INVALID_IMO and INVALID_COORDINATES) |
| `naudisha/api/main.py` | Added `ws_router` to FastAPI application |
| `tests/test_api.py` | Updated and added unit & integration tests covering all contract v2 requirements |
| `current_prompt_implementation_walkthrough.md` | Updated walkthrough for Phase 8.4 |
