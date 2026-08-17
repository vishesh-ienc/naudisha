# NauDisha — Project Progress & Technical Architecture Log

This document provides a comprehensive technical log of all architectural milestones, completed backend modules, implemented API routes, data integrations, and future roadmap items for **NauDisha — Dynamic Maritime Route Optimization Platform** (SIH Project).

---

## 🗺 1. System Architecture & Component Flow

The backend is architected as a modular, high-performance nautical engineering and optimization engine:

```text
                                [ Live External Providers ]
          ┌───────────────────────────────────┼──────────────────────────────────┐
          │                                   │                                  │
          ▼                                   ▼                                  ▼
[ Copernicus Marine (CMEMS) ]      [ Open-Meteo Wind API ]         [ Open AIS & Wikidata SPARQL ]
(Ocean Currents uo/vo & Waves)    (10m Wind Speed & Bearing)      (Live GPS AIS & Vessel Specs)
          │                                   │                                  │
          └───────────────────────────────────┼──────────────────────────────────┘
                                              │
                                              ▼
                             [ Data Providers & Cache Layer ]
                             (CompositeEnvironmentalProvider,
                              VesselProvider, LiveAISManager)
                                              │
                                              ▼
                                 [ Derived Nautical Engine ]
                            (Spherical Haversine, Great-Circle,
                             Vector Decomp, Speed-Over-Ground)
                                              │
                                              ▼
                                    [ Cost Scoring Engine ]
                            (Multi-Objective Normalized [0, 1]:
                             Time, Fuel, Wind, Wave, Current, Safety)
                                              │
                                              ▼
                              [ Geographic Grid Graph Layer ]
                            (GeographicGridGraph, 4-Direction Edges,
                             O(1) Incremental Environmental Updates)
                                              │
                                              ▼
                              [ D* Lite Dynamic Pathfinding ]
                            (Koenig & Likhachev Incremental Search,
                             Reverse Goal-Directed Heuristic Repair)
                                              │
                                              ▼
                                  [ FastAPI REST & WS Layer ]
                            (MVP API Contract v2, OpenAPI Docs,
                             WebSocket Live Navigation Channels)
```

---

## 📁 2. Codebase Organization & File Map

The repository is structured with a dedicated `backend/` directory ready to sit alongside `frontend/`:

```text
naudisha/
├── backend/
│   ├── naudisha/
│   │   ├── api/                     # REST Controllers, Routes, Schemas, Errors
│   │   │   ├── __init__.py
│   │   │   ├── errors.py            # Standardized RFC 7807 error handlers
│   │   │   ├── main.py              # FastAPI app factory, CORS, dotenv loader
│   │   │   ├── routes.py            # API endpoints (/health, /api/ships, /api/routes, etc.)
│   │   │   ├── schemas.py           # Pydantic v2 schemas & ISO 8713 validation
│   │   │   └── services.py          # Route preview orchestration & D* Lite integration
│   │   ├── core/                    # Nautical Math & Hydrodynamic Models
│   │   │   ├── __init__.py
│   │   │   ├── calculations.py      # Haversine, bearing, relative angles, current vector math
│   │   │   ├── models.py            # ShipProfile, EnvironmentalData, CostWeights, Waypoints
│   │   │   └── normalization.py     # Linear & logarithmic [0, 1] normalization utilities
│   │   ├── cost/                    # Multi-Objective Scoring Framework
│   │   │   ├── __init__.py
│   │   │   ├── model.py             # CostModel aggregator with math.inf obstacle safety
│   │   │   └── scorers.py           # 6 individual component scorers (time, fuel, wave, etc.)
│   │   ├── data/                    # Live Marine & Weather Data Ingestion
│   │   │   ├── __init__.py
│   │   │   ├── composite_provider.py# Environmental provider aggregator (Currents+Waves+Winds)
│   │   │   ├── copernicus_provider.py# CMEMS real ocean current & spectral wave fetcher
│   │   │   ├── copernicus_schema.py # CMEMS dataset specifications & vector conversions
│   │   │   ├── vessel_provider.py   # Wikidata SPARQL, Live AIS manager, Curated Registry
│   │   │   ├── weather_provider.py  # Abstract WeatherProvider & batch query interfaces
│   │   │   └── wind_provider.py     # Open-Meteo global atmospheric wind provider
│   │   └── routing/                 # Dynamic Graph & Pathfinding Layer
│   │       ├── __init__.py
│   │       ├── dstar_lite.py        # Koenig-Likhachev D* Lite incremental shortest path
│   │       └── graph.py             # GeographicGridGraph, node navigability, edge weights
│   ├── tests/                       # Automated Test Suite (162 Deterministic Tests)
│   │   ├── test_api.py              # Full REST & WebSocket contract validation
│   │   ├── test_calculations.py     # Nautical math & bearing tests
│   │   ├── test_copernicus_batch_provider.py # Spatial bounding-box batch tests
│   │   ├── test_copernicus_metadata.py # CMEMS schema validation
│   │   ├── test_copernicus_provider.py # CMEMS unit tests with mocks
│   │   ├── test_cost_model.py       # Multi-objective weight aggregation tests
│   │   ├── test_dstar_lite.py       # D* Lite algorithm & key updates tests
│   │   ├── test_dstar_lite_correctness.py # Mathematical optimality & Dijkstra parity tests
│   │   ├── test_dynamic_replanning.py # Dynamic forecast changes & path repair tests
│   │   ├── test_graph.py            # Grid generation & O(1) edge update tests
│   │   ├── test_grid_environment_integration.py # Graph + Weather integration tests
│   │   ├── test_normalization.py    # Math bounds & clamp tests
│   │   ├── test_scorers.py          # 6 component scorer tests
│   │   ├── test_vessel_provider.py  # Real IMO lookup & live AIS manager tests
│   │   └── test_wind_provider.py    # Open-Meteo wind query & caching tests
│   ├── examples/                    # Runnable Demos & Live Verification Tools
│   │   ├── benchmark_copernicus_batching.py # CMEMS query performance benchmark
│   │   ├── fetch_combined_environmental_sample.py # Combined marine sample utility
│   │   ├── fetch_copernicus_sample.py # Live CMEMS query sample
│   │   ├── fetch_wind_sample.py     # Open-Meteo wind query sample
│   │   ├── run_dstar_lite_demo.py   # CLI pathfinding demonstration
│   │   ├── run_dynamic_replanning_demo.py # Live dynamic obstacle replanning demo
│   │   ├── run_grid_environment_demo.py # 2D geographic grid visualization
│   │   ├── run_live_api_route_demo.py # Live route preview CLI test
│   │   ├── run_live_batch_grid_demo.py # Live batch environment sampling demo
│   │   ├── run_live_grid_routing_demo.py # End-to-end live marine routing demo
│   │   ├── run_segment_cost.py      # Single segment cost calculator demo
│   │   ├── verify_aisstream_key.py  # AISStream WebSocket test tool
│   │   ├── verify_copernicus_access.py # CMEMS access check tool
│   │   ├── verify_copernicus_credentials.py # CMEMS authentication verification
│   │   └── verify_deployed_api.py   # Public/local API health probe & contract suite
│   ├── pyproject.toml               # Package build, dependencies, and entrypoints
│   ├── .env.example                 # Environment variable template
│   └── README.md                    # Backend setup & execution documentation
├── docs/                            # Single Source of Truth Specifications
│   ├── API_CONTRACT.md              # Authoritative MVP API Contract v2
│   ├── FRONTEND_API_HANDOFF.md      # Frontend developer integration guide
│   └── FRONTEND_DEVELOPMENT_WORKFLOW.md # Development conventions & workflow
├── current_prompt_implementation_walkthrough.md # Per-prompt log & audit records
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 3. Implemented API Endpoints (MVP Contract v2)

All endpoints conform strictly to [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md):

| Method | Route | Description | Live Status |
|---|---|---|---|
| `GET` | `/health` | Liveness check; returns `{ "status": "ok", "service": "naudisha-backend" }` | ✅ Verified |
| `GET` | `/ready` | Readiness check; verifies internal environmental providers | ✅ Verified |
| `POST` | `/api/ships` | Real vessel lookup by IMO number with live AIS position & status | ✅ Verified (Real Data) |
| `POST` | `/api/routes/preview` | Multi-objective route optimization with live Copernicus & Open-Meteo data | ✅ Verified (Live Math) |
| `POST` | `/api/ships/{imo_number}/tracking/start` | Initiates live tracking & replanning session for a vessel | ✅ Verified |
| `POST` | `/api/ships/{imo_number}/tracking/stop` | Terminates active vessel tracking session | ✅ Verified |
| `WS` | `/ws/ships/{imo_number}` | Real-time WebSocket for bidirectional ship position & replan streaming | ✅ Verified |

---

## 🌊 4. External Data Source Integrations Status

| Data Layer | External Provider | Integration Mechanism | Status | Notes |
|---|---|---|---|---|
| **Ocean Currents** | **Copernicus Marine Service (CMEMS)** | Physics API (`uo`, `vo` surface vectors) via `copernicusmarine` toolbox | **100% Real & Active** | Authenticated with user `vjiwnani`. Fallbacks to open vectors when offline. |
| **Ocean Waves** | **Copernicus Marine Service (CMEMS)** | Waves API ($H_s$ wave height, $T_p$ peak period, wave direction) | **100% Real & Active** | Real-time spectral wave observations. |
| **Atmospheric Wind** | **Open-Meteo Marine API** | ECMWF / GFS 10m wind speed & wind direction forecast | **100% Real & Active** | Free, open API with geographic coordinate caching. |
| **Vessel Master Specs** | **Wikidata SPARQL Endpoint** | Live SPARQL queries on `wdt:P458` (IMO) for LOA, beam, draft, class | **100% Real & Active** | Resolves any valid commercial ship worldwide. |
| **Live AIS GPS Feeds** | **Digitraffic Open Maritime AIS** | Live REST GeoJSON feed of active commercial satellite/terrestrial transponders | **100% Real & Active** | Real-time live GPS coordinates, SOG, COG, and nav status. |
| **Global Satellite AIS** | **AISStream.io** | WebSocket streaming feed (`wss://stream.aisstream.io/v0/stream`) | **Configured** | Activated via `AISSTREAM_API_KEY` in `.env`. |

---

## 🧩 5. Completed Technical Milestones

### Phase 1 — Mathematical & Hydrodynamic Foundation
* Spherical Haversine distance and great-circle initial forward bearing.
* Relative angle vector decomposition for wind, waves, and ocean currents.
* Effective Speed Over Ground (SOG) with current assistance/resistance and safety limits.
* Six modular component scorers normalized to $[0.0, 1.0]$.
* Multi-objective weighted cost model with `math.inf` obstacle boundary conditions.

### Phase 2 — Spatial Grid & Routing Environment Layer
* 2D `GeographicGridGraph` with 4-direction vector edges.
* $O(1)$ dynamic edge environment updates and vertex navigability toggles.
* Successor and predecessor query interfaces for incremental graph search.

### Phase 3 — D* Lite Incremental Pathfinding Engine
* Koenig & Likhachev $D^*$ Lite algorithm with lexicographic key priority queue.
* One-step lookahead $rhs(u)$ and cost-to-goal $g(u)$ tracking with lazy min-heap deletion.
* Mathematical heuristic admissibility audit ensuring optimal path guarantees ($h(u, v) \le c^*(u, v)$).
* Dynamic graph replanning repairing shortest path trees incrementally without full re-computation.

### Phase 4 — Marine & Atmospheric Data Ingestion Pipeline
* `WeatherProvider` interface with single-point and spatial bounding-box batch querying (`BatchCapableProvider`).
* `OpenMeteoWindProvider` with timestamp normalization and in-memory cache.
* `CopernicusMarineProvider` connecting to real CMEMS ocean current & wave datasets.
* `CompositeEnvironmentalProvider` stitching current, wave, and wind data into unified `EnvironmentalData`.

### Phase 5 — API Layer & MVP Contract v2 Alignment
* FastAPI application factory with universal CORS and RFC 7807 error envelopes.
* Pydantic v2 schemas with ISO 8713 checksum validation for 7-digit IMO numbers.
* Service orchestration for route previewing with live environmental graph cost evaluation.
* Complete alignment with authoritative `docs/API_CONTRACT.md`.

### Phase 6 — Universal Vessel Identity & Live AIS Architecture
* Decoupled `VesselProvider` and `LiveAISManager` hierarchy.
* Live Wikidata SPARQL endpoint integration resolving master particulars dynamically.
* Curated commercial vessel registry with accurate historical fixtures (*Ever Given*, *Shinsung Dream*, *Courage*, *EVALI*, *Berge Everest*).
* Digitraffic real-time open AIS provider streaming live GPS coordinates.
* Strict separation of static particulars and live AIS (returning `position: null` when no transponder signal is transmitting, avoiding fabricated coordinates).

### Phase 7 — Repository Monorepo Reorganization
* Restructured backend into dedicated `backend/` folder.
* Removed temporary scratch test scripts and streamlined `backend/examples/`.
* 162 deterministic unit tests passing 100% offline.
* Merged and pushed clean state to `main`.

### Phase 14 — Objective-Driven Indian Ocean Route Optimization
* Evolved Plan Voyage into an objective-driven planning engine with 4 optimization presets: **Fuel Efficiency**, **Fastest Voyage**, **Safety & Weather**, and **Balanced Route**.
* Implemented `objective_to_weights` in `backend/naudisha/api/services.py` with mathematically calibrated weights and strict safety floor invariant ($\ge 1.0$).
* Extended `RoutePreviewRequest` and `RoutePreviewResponse` with `optimization_objective` and `cost_weights`.
* Updated `PlanningManager.signature()` cache key to segregate cached routes by objective.
* Created interactive `ObjectiveSelector` UI component with real-time feedback and dynamic descriptions.
* Added truthful D* Lite Cost Engine Weight Distribution panel in `CalculationConsole` with proportional stacked bar chart and dimension percentages.
* Expanded port database with major East Africa and Western Indian Ocean shipping hubs (Mombasa, Dar es Salaam, Port Louis, Victoria, Toamasina, Maputo, Durban, Richards Bay).

### Phase 15 — Route Optimization Performance & Speed Improvement
* **Open-Meteo Multi-Coordinate Batch API**: Implemented native comma-separated multi-location batch queries (`fetch_wind_batch`), reducing Open-Meteo network query time from ~23.4s to ~1s. Added exponential backoff and jitter for rate-limiting resilience.
* **Concurrent Environmental Ingestion**: Parallelized Copernicus Marine and Open-Meteo fetching in `CompositeEnvironmentalProvider` using `ThreadPoolExecutor`, completely hiding wind query latency inside the marine data fetch window.
* **Midpoint Spatial Deduplication**: Deduplicated edge midpoints in `GeographicGridGraph.populate_environment()`, cutting grid condition requests across bidirectional edges by 50%.
* **Vectorized `cKDTree` Nearest Neighbor Extraction**: Replaced 4,200 iterative Pandas DataFrame `.idxmin()` and distance checks with sub-millisecond SciPy `cKDTree` spatial index lookups, reducing DataFrame processing time from ~3s to < 2ms.
* **Temporal Spatial In-Memory Cache**: Cached environmental conditions with hourly departure-time bucketing. Switching objectives on the same voyage corridor (e.g. Balanced $\to$ Fuel Efficiency $\to$ Fastest) recalculates optimal routes in **< 20 ms**.
* **Real Progress Stage Streaming**: Instrumented stage transitions (`building_grid`, `sampling_environment`, `evaluating_costs`, `solving_dstar`, `reconstructing_route`, `ready`) in `PlanningManager`, exposing truthful progress to the frontend `CalculationConsole`.

---

## 🧪 7. Test Suite Status

```text
Ran 231 tests in 2.616s
OK (231 passed, 0 failed, 0 errors)
```
* **Coverage:** Nautical math, cost scoring, objective weighting, grid graph, D* Lite pathfinding, CMEMS schemas, wind providers, universal vessel lookup, live AIS manager, asynchronous planning jobs, batch environmental fetching, cKDTree extraction, and REST/WebSocket API endpoints.
* **Determinism:** 100% offline reproducible with zero unmocked network dependencies during test execution.
