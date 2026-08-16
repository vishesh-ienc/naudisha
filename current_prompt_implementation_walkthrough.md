# Current Prompt Walkthrough: Phase 8.7 — Real Vessel Data & Live AIS Provider Integration

## 1. Goal

Integrate real open maritime data sources and live AIS transponder feeds into `POST /api/ships` while conforming to MVP API Contract v2, correcting misleading static fixtures, separating static particulars from dynamic GPS coordinates, and ensuring zero mock regressions.

---

## 2. Working Branch & Git Rules

* **Branch:** `feature/backend-api`
* **Rule:** `main` is completely untouched.
* **Commit:** Concise 2-line commit message on `feature/backend-api`.

---

## 3. Implementation Details

### A. Provider Hierarchy & Data Sources
1. **Tier 1: Master Registry (`RegistryVesselProvider`)**:
   - Curated master records for major global commercial vessels.
   - Corrected IMO `9176187` to *Shinsung Dream* (General Cargo Vessel, 106.0m x 18.0m, draft 7.0m).
   - Mapped *Courage* (Vehicles Carrier, 199.9m x 32.2m, draft 8.8m) to its true IMO `8916968`.
   - All static positions set to `None` so static data is never presented as live AIS.
2. **Tier 2: Live Wikidata SPARQL (`WikidataVesselProvider`)**:
   - Queries open Wikidata SPARQL endpoint (`wdt:P458`) for real-world vessel identity, ship class, and naval dimensions.
3. **Tier 3: Live AIS Manager (`LiveAISManager`)**:
   - Ingests real-time satellite/terrestrial AIS reports (`AISDataRecord`).
   - Maps MMSI and IMO to live GPS coordinates and navigational statuses.
   - Enforces a 24-hour staleness threshold (`86400` seconds). Stale or missing AIS signals return `position: null` with `status: "unknown"`.
4. **Tier 4: Hydrodynamic Synthesizer (`SyntheticVesselProvider`)**:
   - Fallback for uncataloged valid IMOs. Returns realistic dimensions with `position: null` and `source="synthetic"`.
5. **Composite Orchestrator (`CompositeVesselProvider`)**:
   - Manages in-memory particulars caching (TTL: 7 days / 604,800s) and merges live AIS transponder positions onto static vessel profiles.

### B. Route Planning Integration (`POST /api/routes/preview`)
- Ingests real vessel profile particulars (LOA, beam, draft, cruising speed, max speed) from the vessel provider directly into D* Lite dynamic cost routing.

---

## 4. Real IMO Test Verification

| IMO Number | Real Vessel Name | Type | LOA x Beam x Draft | Live AIS GPS Status |
|---|---|---|---|---|
| **`9811000`** | **Ever Given** | Container Ship (Golden-class) | 399.9m x 58.8m x 14.5m | Active / Streamable |
| **`9176187`** | **Shinsung Dream** | General Cargo Vessel | 106.0m x 18.0m x 7.0m | `null` (Static Master Data) |
| **`8916968`** | **Courage** | Vehicles Carrier / Ro-Ro | 199.9m x 32.2m x 8.8m | `null` (Static Master Data) |
| **`9400980`** | **EVALI** | Crude Oil Tanker (Aframax) | 228.6m x 42.0m x 15.0m | `null` (Static Master Data) |
| **`9074729`** | **Diamond A** | Commercial Cargo Vessel | 159.9m x 24.6m x 9.5m | `null` (Wikidata Resolved) |
| **`9999993`** | **Vessel IMO-9999993** | Bulk Carrier | 213.0m x 29.2m x 12.3m | `null` (Synthesized Fallback) |
| **`1234560`** | *(Invalid Checksum)* | N/A | N/A | HTTP 422 `INVALID_IMO` |

---

## 5. Verification & Tests

* **Unit Test Suite:** `python -m unittest discover -s tests` -> **162 passed, 0 failed, 0 errors**.
* **Offline Determinism:** All external network calls mocked in unit tests; tests run with zero internet dependency.
* **Git Status:** Clean. Only files in `feature/backend-api` modified.
