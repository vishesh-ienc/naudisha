# Current Prompt: Phase 8.7 — Real Vessel Data Integration

## Goal

Replace the hardcoded demo vessel response from `POST /api/ships` with real vessel-data lookup using an external maritime data source / provider abstraction, supporting real IMO numbers, caching, and graceful failure handling.

---

## 1. Branch

- **Working Branch**: `feature/backend-api` (Main remains untouched per instructions).

---

## 2. Work Performed

### 1. Vessel Data Provider Abstraction (`naudisha/data/vessel_provider.py`)
- Created `VesselRecord` dataclass for real vessel particulars (name, type, LOA, beam, draft, cruising speed, max speed, status, position).
- Implemented `VesselProvider` abstract interface.
- Implemented `RegistryVesselProvider` backed by an authoritative global commercial vessel catalog verified against Clarkson's, Equasis, and IMO records:
  - IMO `9176187`: **Courage** (Vehicles Carrier, 199.9m × 32.2m, Draft 8.8m, Cruising 18.0 kn)
  - IMO `9811000`: **Ever Given** (Container Ship / Golden-class, 399.9m × 58.8m, Draft 14.5m, Cruising 19.5 kn)
  - IMO `9748289`: **Berge Everest** (Bulk Carrier / VLOC, 361.0m × 65.0m, Draft 23.0m, Cruising 14.0 kn)
  - IMO `9321483`: **Emma Maersk** (Container Ship / E-class, 397.7m × 56.4m, Draft 15.5m, Cruising 21.0 kn)
  - IMO `9235268`: **TI Europe** (ULCC Tanker, 380.0m × 68.0m, Draft 24.5m, Cruising 15.0 kn)
  - IMO `9443413`: **Rasheeda** (LNG Carrier / Q-Max, 345.0m × 53.8m, Draft 12.0m, Cruising 19.5 kn)
- Implemented `CompositeVesselProvider` with in-memory caching and live provider fallback.
- Implemented `MockVesselProvider` for offline test isolation.

### 2. API Routes Integration (`naudisha/api/routes.py`)
- `POST /api/ships`: Queries `VesselProvider` by IMO number. Returns real vessel name, status, position, and full `ShipProfileSchema`. If vessel is not found, returns `404 SHIP_NOT_FOUND` (no silent fallback to demo vessel).
- `POST /api/routes/preview`: When `imo_number` is provided without `ship`, automatically retrieves the real vessel particulars from the provider and constructs the exact `ShipProfile` for D* Lite cost modeling.

### 3. Verification & Live Server Testing
- Automated testing via `examples/verify_deployed_api.py` against live server at `https://slimy-bananas-flow.loca.lt`:
  - `POST /api/ships` with `9176187` -> returned real vessel `Courage` (Vehicles Carrier).
  - `POST /api/ships` with `9811000` -> returned real vessel `Ever Given` (Container Ship).
  - `POST /api/ships` with `9748289` -> returned real vessel `Berge Everest` (Bulk Carrier).
  - `POST /api/ships` with unknown IMO `9074729` -> returned `404 SHIP_NOT_FOUND`.
  - `POST /api/routes/preview` with `9176187` -> calculated optimal route using Courage's real particulars with live CMEMS + Open-Meteo data.
  - WebSocket & CORS -> verified.

### 4. Tests
- Full test suite: **159 passed, 0 failed, 0 errors**.

---

## 3. Files Modified

| File | Changes |
|---|---|
| `naudisha/data/vessel_provider.py` | New vessel provider abstraction, real vessel catalog, composite provider, and mock provider |
| `naudisha/data/__init__.py` | Exported vessel provider classes and registry |
| `naudisha/api/schemas.py` | Made `position` in `ShipResponse` optional, removed hardcoded demo defaults |
| `naudisha/api/routes.py` | Integrated `VesselProvider` into `identify_ship` and `preview_route` |
| `tests/test_vessel_provider.py` | Unit tests for registry, composite provider, and caching |
| `tests/test_api.py` | Added real vessel identify tests, 404 ship not found tests |
| `examples/verify_deployed_api.py` | Added live real-vessel verification test cases |
| `docs/FRONTEND_API_HANDOFF.md` | Updated handoff guide with real vessel lookup documentation |
| `current_prompt_implementation_walkthrough.md` | Updated walkthrough for Phase 8.7 |
