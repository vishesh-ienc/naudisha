# Current Prompt Walkthrough: Phase 8.6.1 — Audit Vessel IMO Data Source Before Integration

## 1. Goal

Perform a complete audit and execution trace of `POST /api/ships` to determine how vessel data is queried, why IMO `9176187` returned `Courage`, separate static particulars from live AIS requirements, and evaluate backend provider readiness without modifying code.

---

## 2. Working Branch & Git Rules

* **Branch:** `feature/backend-api`
* **Rule:** `main` is completely untouched (no checkouts, merges, or pushes to `main`).
* **Implementation Changes:** Zero code changes (audit/investigation only).

---

## 3. Findings & Trace

### A. Execution Trace for `POST /api/ships`
```text
POST /api/ships
   │
   ▼
naudisha/api/routes.py :: identify_ship()
   │  (decodes JSON payload into ShipIdentifyRequest & validates ISO 8713 checksum)
   │
   ▼
naudisha/api/routes.py :: get_vessel_provider()
   │  (injects singleton CompositeVesselProvider)
   │
   ▼
naudisha/data/vessel_provider.py :: CompositeVesselProvider.get_vessel_by_imo()
   ├──► 1. In-Memory Cache (_cache dict)
   ├──► 2. Mock Provider (if injected for unit tests)
   ├──► 3. RegistryVesselProvider (queries GLOBAL_VESSEL_REGISTRY dictionary)
   ├──► 4. WikidataVesselProvider (queries live open SPARQL endpoint)
   └──► 5. SyntheticVesselProvider (fallback naval architecture synthesizer)
   │
   ▼
naudisha/api/schemas.py :: ShipResponse
   │  (serializes IMO, name, status, position, and ShipProfileSchema)
   │
   ▼
JSON HTTP 200 Response
```

### B. Why IMO `9176187` Returned `Courage`
* **Source:** In `naudisha/data/vessel_provider.py` (lines 43–56), `GLOBAL_VESSEL_REGISTRY` contains a static entry mapping key `"9176187"` to `Courage`.
* **Root Cause:** When `CompositeVesselProvider` queries `RegistryVesselProvider`, it hits key `"9176187"` in Tier 1 before querying external providers.
* **Discrepancy:** The real vessel for IMO `9176187` is *SHINSUNG DREAM* (General Cargo Vessel, LOA 106.0 m). The vehicle carrier *Courage* has IMO `8916962`. The static test fixture conflated the IMO with the car carrier *Courage*.

### C. Static Particulars vs. Live AIS Fields

| Field | Current Source | Real-Time? | Correct for IMO 9176187? |
|---|---|---|---|
| **Name** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (*Courage* vs *Shinsung Dream*) |
| **Ship type** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (*Vehicles Carrier* vs *General Cargo*) |
| **Length** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (`199.9 m` vs `106.0 m`) |
| **Beam** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (`32.2 m` vs `18.0 m`) |
| **Draft** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (`8.8 m` vs `7.0 m`) |
| **Cruising speed** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (`18.0 kn` vs `12.5 kn`) |
| **Max speed** | `GLOBAL_VESSEL_REGISTRY` (Dict) | No (Static) | ❌ Conflated (`20.5 kn` vs `14.0 kn`) |
| **Latitude** | Hardcoded in Dict | No (Static) | ❌ Static coordinate (`18.52`) |
| **Longitude** | Hardcoded in Dict | No (Static) | ❌ Static coordinate (`72.91`) |
| **Status** | Hardcoded in Dict | No (Static) | ⚠️ Generic `"underway"` |

### D. Provider Readiness
* **`IMO → vessel particulars`**: Ready. Abstract base class `VesselProvider` decouples the API controller from data sources.
* **`IMO → live AIS position/status`**: Ready. Domain model supports `position: Optional[Coordinate] = None` and live WebSocket streaming.

---

## 4. Verification

* **Unit Tests:** `python -m unittest discover -s tests` -> **159 passed, 0 failed, 0 errors**.
* **Git Branch:** `feature/backend-api`
* **Git Status:** Clean. No implementation modifications made in this phase.
