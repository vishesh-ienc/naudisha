# NauDisha — API Contract Addendum Proposal

**Status:** Proposal — awaiting backend review
**Raised by:** Frontend
**Target:** `docs/API_CONTRACT.md` v2
**Reviewed against:** `feature/backend-api` @ `af2efcd`

---

## 1. Purpose

This document lists gaps found in `docs/API_CONTRACT.md` while planning the frontend
against the existing backend implementation on `feature/backend-api`.

Each item below states:

- **The problem**
- **Evidence** — the specific file/behaviour in the current codebase
- **Proposed change**
- **Why it matters**

Nothing here is a criticism of the current implementation. The backend foundation is
clean and correctly layered. These are contract-level gaps that surface only when you
try to build the full user flows end to end.

---

## 2. Compatibility guarantee

**Every change proposed here is additive.** No existing field is renamed, removed, or
has its type changed. An existing client written against v1 of the contract will keep
working unchanged.

**The frontend will treat every field in this document as optional.** The current
contract is the guaranteed baseline. If `legs` is absent we render a plain polyline;
if `alerts` is absent we show the bare `reason` string; if `ship` is absent we fall
back to prompting the user. Nothing in the frontend breaks if you adopt none of this,
or only part of it.

Adopt these item by item. Use the sign-off table in section 10.

---

## 3. What the backend currently implements

Read from `feature/backend-api` @ `af2efcd`:

| Endpoint | Contract | Status |
| :--- | :--- | :--- |
| `GET /health` | ❌ not in contract | ✅ implemented |
| `POST /api/ships` | ✅ §4 | ✅ implemented (static demo response) |
| `POST /api/routes/preview` | ✅ §5 | ✅ implemented (real D* Lite) |
| `POST /api/ships/{imo}/tracking/start` | ✅ §6 | ⬜ not yet |
| `GET /api/ships/{imo}/status` | ✅ §7 | ⬜ not yet |
| `GET /api/ships/{imo}/route` | ✅ §8 | ⬜ not yet |
| `WS /ws/ships/{imo}` | ✅ §9 | ⬜ not yet |

The frontend will mock the four unimplemented endpoints against the contract shape
and swap to live calls as they land. No coordination needed — just tell us when one
is ready.

---

## 4. Priority summary

| # | Issue | Priority | Backend effort |
| :--- | :--- | :--- | :--- |
| P0-1 | `departure_time` missing from route preview | **Blocker** | ~3 lines |
| P0-2 | Ship particulars absent from entire contract | **Blocker** | Medium |
| P0-3 | No IMO-less routing flow | **Blocker** | Small |
| P1-1 | Hazard/alert payload missing | High | Medium |
| P1-2 | `destination` missing from tracking responses | High | Small |
| P1-3 | `tracking/start` has no request body | High | Small |
| P1-4 | IMO validation mismatch (frontend vs backend) | High | ~1 line |
| P2-1 | `/health` undocumented | Medium | Doc only |
| P2-2 | `total_cost` has no interpretable scale | Medium | Small |
| P2-3 | Per-leg data not exposed (already computed) | Medium | Small |
| P2-4 | Default timestamp hardcodes 12:00 UTC | Medium | ~1 line |
| P2-5 | `total_cost` unit inconsistent on fallback path | Low | ~1 line |

---

## 5. P0 — Blockers

These three prevent user flows described in `FRONTEND_DEVELOPMENT_WORKFLOW.md` from
being built at all.

### P0-1 — `departure_time` is missing from `POST /api/routes/preview`

**Problem.** The request accepts only `imo_number`, `start`, `destination`. There is
no way to say *when* the voyage departs.

**Evidence.** `naudisha/api/services.py` — `plan_preview_route()` **already accepts a
`timestamp` parameter**:

```python
def plan_preview_route(
    self, imo_number, start_lat, start_lon, dest_lat, dest_lon,
    timestamp: Optional[Union[datetime, str]] = None,   # <-- already here
) -> RoutePlanResult:
```

…and correctly forwards it to `graph.populate_environment(timestamp=ts, ...)`.

But `RoutePreviewRequest` in `schemas.py` has no `departure_time` field, and
`routes.py` never passes one. **The plumbing is already built — it just isn't wired
to the API surface.**

**Why it matters.** Copernicus Marine and Open-Meteo are *forecast* services. Without
a departure time the backend samples "now", so planning a voyage that departs in
three days routes it through *today's* weather. Flow B ("Plan a Voyage") is
scientifically meaningless without this.

It also blocks absolute ETA display. `estimated_time_hours: 6.51` is a duration; the
frontend cannot render "arrives 20 Aug 14:30 UTC" without knowing when the clock starts.

**Proposed change.**

```jsonc
// POST /api/routes/preview — request
{
  "imo_number": "1234567",
  "start": { "latitude": 18.52, "longitude": 72.91 },
  "destination": { "latitude": 19.07, "longitude": 72.87 },
  "departure_time": "2026-08-20T06:00:00Z"   // NEW — optional, defaults to now
}
```

```jsonc
// POST /api/routes/preview — response
{
  ...,
  "departure_time": "2026-08-20T06:00:00Z",  // NEW — echo back what was used
  "eta": "2026-08-20T12:30:00Z"              // NEW — departure + estimated_time_hours
}
```

Forecast horizons are finite (Open-Meteo ~16 days, CMEMS ~10 days). A departure time
beyond the horizon should fail cleanly — see new error code
`DEPARTURE_TIME_OUT_OF_RANGE` in section 8.

---

### P0-2 — Ship particulars appear nowhere in the contract

**Problem.** The cost model cannot run without a `ShipProfile`. The contract never
carries one.

**Evidence.** `naudisha/core/models.py` — `ShipProfile` requires six fields, all of
which feed the scorers:

```python
ship_type: str
length: float           # metres (LOA)
beam: float             # metres
draft: float            # metres
cruising_speed: float   # knots
maximum_speed: float    # knots
```

`naudisha/api/services.py` currently hardcodes a single vessel for **every** request:

```python
self.ship_profile = ship_profile or ShipProfile(
    ship_type="Container Vessel (Panamax)",
    length=294.0, beam=32.2, draft=12.0,
    cruising_speed=18.0, maximum_speed=23.0,
)
```

The `imo_number` is accepted, validated, and echoed back in the response — but it is
**never used to look up vessel characteristics**. Today a 400 m ULCC and a 90 m coastal
tanker produce byte-identical routes.

**Why it matters.** Three of six scorers depend directly on these fields:
`fuel_score` uses the speed ratio, `safety_score` uses design operating limits, and
draft is what should gate navigability in shallow water. Routing is currently
vessel-agnostic, which undercuts the core claim of the project.

It also blocks the requirement that details unavailable from an IMO lookup are
collected from the user — there is no field for them to travel in.

**Proposed change.** Add a `ship` object, and make `POST /api/ships` report what it
knows and what it is missing:

```jsonc
// POST /api/ships — response
{
  "imo_number": "1234567",
  "name": "Demo Vessel",
  "status": "underway",
  "position": { "latitude": 18.52, "longitude": 72.91 },

  "ship": {                              // NEW — nulls where unknown
    "ship_type": "Container Vessel (Panamax)",
    "length_m": 294.0,
    "beam_m": 32.2,
    "draft_m": null,
    "cruising_speed_kn": 18.0,
    "max_speed_kn": null
  },
  "source": "registry",                  // NEW — "registry" | "ais" | "defaults"
  "missing_fields": ["draft_m", "max_speed_kn"]   // NEW
}
```

`missing_fields` is what the frontend uses to build the manual-entry form. It asks
the user for exactly the fields you could not resolve, and nothing more. If you return
`source: "defaults"`, the frontend labels the vessel data as assumed rather than looked up.

The same `ship` object becomes an optional field on `POST /api/routes/preview`,
carrying user-supplied values back to you.

> **Naming note.** The proposal uses explicit unit suffixes (`length_m`,
> `cruising_speed_kn`) rather than the bare engine names (`length`, `cruising_speed`).
> Ambiguous units are a classic source of bugs across an HTTP boundary. Happy to drop
> the suffixes if you prefer to mirror `ShipProfile` exactly — your call, just tell us
> which and we will match it.

---

### P0-3 — No IMO-less routing flow

**Problem.** `imo_number` is required on both `POST /api/ships` and
`POST /api/routes/preview`.

**Evidence.** `schemas.py` — both `RoutePreviewRequest` and `ShipIdentifyRequest`
declare `imo_number: str = Field(...)` (required) with a validator that rejects empty
strings.

**Why it matters.** A user should be able to evaluate a route without naming a real
vessel — for planning, comparison, or simply because they do not have an IMO to hand.
This is a required product flow.

**Proposed change.** Make `imo_number` optional on `POST /api/routes/preview` when a
`ship` object is supplied:

```jsonc
{
  "imo_number": null,          // now OPTIONAL
  "ship": {                    // required when imo_number is absent
    "ship_type": "Bulk Carrier",
    "length_m": 225.0, "beam_m": 32.2, "draft_m": 12.5,
    "cruising_speed_kn": 14.0, "max_speed_kn": 17.0
  },
  "start": { ... },
  "destination": { ... },
  "departure_time": "2026-08-20T06:00:00Z"
}
```

Validation rule: **at least one of `imo_number` or `ship` must be present.** If
neither, return `SHIP_PARTICULARS_REQUIRED` (section 8).

---

## 6. P1 — High priority

### P1-1 — Hazard/alert payload is missing

**Problem.** The `route_update` message carries one field to explain a reroute:

```json
"reason": "environment_changed"
```

A bare string. No severity, no location, no radius, no hazard type.

**Why it matters.** The frontend is required to show the user *what* is ahead and
*where* — a danger zone on the map, a severity-coloured alert, a reason for the
detour. None of that can be rendered from a single string. Right now the best the UI
can do is display the raw text, which does not communicate risk.

**Proposed change.** Add an optional `alerts` array to `route_update`:

```jsonc
{
  "type": "route_update",
  "timestamp": "2026-08-16T06:35:00Z",
  "position": { "latitude": 18.61, "longitude": 72.95 },
  "route": [ ... ],
  "distance_nm": 108.32,
  "estimated_time_hours": 6.01,
  "total_cost": 15.42,
  "reason": "hazard_detected",

  "alerts": [                                    // NEW
    {
      "id": "alert_001",
      "severity": "critical",                    // "critical" | "warning" | "info"
      "kind": "storm",                           // see enum below
      "message": "Severe storm ahead — 45 kn winds, 5.5 m significant wave height",
      "position": { "latitude": 18.80, "longitude": 72.60 },
      "radius_nm": 25.0,
      "detected_at": "2026-08-16T06:34:00Z"
    }
  ]
}
```

Suggested `kind` values — extend as needed, the frontend will render unknown kinds
with a neutral icon rather than breaking:

`storm` · `high_waves` · `strong_current` · `headwind` · `non_navigable` ·
`draft_limit` · `forecast_gap`

Suggested `reason` values: `environment_changed` · `hazard_detected` ·
`position_deviation` · `manual_replan` · `forecast_refresh`

---

### P1-2 — `destination` missing from tracking responses

**Problem.** `FRONTEND_DEVELOPMENT_WORKFLOW.md` §5 (Ship Information Panel) requires
displaying the destination. Neither `GET /api/ships/{imo}/status` nor
`GET /api/ships/{imo}/route` returns one.

**Proposed change.** Add `destination` to both, plus `route_status` to `/status`:

```jsonc
// GET /api/ships/{imo}/status
{
  "imo_number": "1234567",
  "status": "underway",
  "position": { "latitude": 18.58, "longitude": 72.94 },
  "timestamp": "2026-08-16T06:30:00Z",
  "destination": { "latitude": 19.07, "longitude": 72.87 },  // NEW, nullable
  "route_status": "optimal"                                   // NEW
}
```

Without it the frontend must infer destination as `route[route.length - 1]`, which
breaks whenever the route is empty, truncated, or unavailable.

---

### P1-3 — `POST /api/ships/{imo}/tracking/start` has no request body

**Problem.** Contract §6 defines no body. When a user previews a voyage and then
clicks "Start Tracking", the backend is never told where the ship is going.

**Proposed change.**

```jsonc
// POST /api/ships/{imo_number}/tracking/start — request
{
  "destination": { "latitude": 19.07, "longitude": 72.87 },  // optional
  "departure_time": "2026-08-20T06:00:00Z",                  // optional
  "ship": { ... }                                            // optional
}
```

All fields optional — an empty body keeps current behaviour for a ship already
underway with a known destination.

---

### P1-4 — IMO validation rules disagree

**Problem.** Three different rules are in play:

| Source | Rule |
| :--- | :--- |
| `API_CONTRACT.md` §3 | 7-digit string, example `"1234567"` |
| `schemas.py` validator | `^\d{6,8}$` — 6 to 8 digits, no checksum |
| ISO 8713 (the real standard) | exactly 7 digits **with a check digit** |

**Why it matters.** If the frontend validates strictly and the backend loosely, users
hit client-side rejections for values the server would accept — or worse, the reverse,
and a malformed IMO reaches the vessel lookup.

**Proposed change.** Both sides adopt **ISO 8713**: exactly 7 digits, where the 7th is
a check digit computed as — multiply the first six digits by weights 7, 6, 5, 4, 3, 2,
sum them, and take the last digit of the sum.

```
IMO 1234567:  1×7 + 2×6 + 3×5 + 4×4 + 5×3 + 6×2 = 77  →  last digit 7  ✓ valid
```

The contract's existing example `"1234567"` is a valid IMO under this rule, so no
fixtures need to change.

Backend change is one line:

```python
@field_validator("imo_number")
@classmethod
def validate_imo(cls, v: str) -> str:
    cleaned = v.strip() if isinstance(v, str) else ""
    if not re.match(r"^\d{7}$", cleaned):
        raise ValueError("IMO number must be exactly 7 digits.")
    if sum(int(d) * w for d, w in zip(cleaned[:6], (7, 6, 5, 4, 3, 2))) % 10 != int(cleaned[6]):
        raise ValueError("IMO number check digit is invalid (ISO 8713).")
    return cleaned
```

The frontend will implement the identical rule so both sides agree exactly.

---

## 7. P2 — Worth doing

### P2-1 — `GET /health` is implemented but undocumented

Good endpoint, missing from the contract. The frontend wants to rely on it as the
backend-availability probe that drives live-vs-mock mode, so please treat it as part
of the contract rather than an internal detail.

```jsonc
// GET /health
{ "status": "ok", "service": "naudisha-backend" }
```

Optional additions that would be genuinely useful: `version`, and a
`providers` block reporting Copernicus/Open-Meteo reachability, so the UI can warn
"environmental data degraded" before a route request fails.

---

### P2-2 — `total_cost` has no interpretable scale

**Problem.** `total_cost: 16.31` is a dimensionless weighted sum of six normalised
scores. It has no unit and no reference point. Displayed on screen it communicates
nothing to a user — and nothing to a judge at evaluation.

**Proposed change.** Return the cost of the naive direct route alongside it:

```jsonc
{
  "total_cost": 15.42,
  "baseline_cost": 18.79,           // NEW — great-circle / direct route cost
  "efficiency_gain_percent": 17.9   // NEW — or let the frontend compute it
}
```

This lets the UI show **"18% more efficient than the direct route"** — a number that
explains itself. It is also the single clearest demonstration that the optimiser is
doing real work, which is hard to convey with a bare `15.42`.

---

### P2-3 — Per-leg data is computed but not exposed

**Problem.** The route is a flat list of coordinates. The frontend cannot show
conditions along the voyage.

**Evidence.** The engine already has all of this. Every `GridEdge` carries
`env_data`, `cost`, and a full `evaluation` — and `services.py` already reads
`edge.evaluation.metrics.distance_nm` and `.travel_time_hours` while summing totals.
The data is in hand and currently discarded.

**Proposed change.** Add an optional `legs` array:

```jsonc
"legs": [
  {
    "from": { "latitude": 18.52, "longitude": 72.91 },
    "to":   { "latitude": 18.65, "longitude": 72.95 },
    "distance_nm": 29.31,
    "travel_time_hours": 1.62,
    "eta": "2026-08-20T07:37:00Z",
    "cost": 2.41,
    "environment": {
      "wind_speed_kn": 18.7, "wind_direction_deg": 261.0,
      "wave_height_m": 2.42, "wave_period_s": 9.8,
      "current_speed_kn": 0.31, "current_direction_deg": 136.0
    }
  }
]
```

This is the highest-value-per-effort item in this document. It unlocks a polyline
colour-graded by segment cost and live weather readouts along the route — the most
visually convincing part of the whole demo — from data you already compute.

---

### P2-4 — Default timestamp hardcodes 12:00 UTC

**Evidence.** `naudisha/api/services.py`:

```python
ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
```

This takes today's *date* but pins the *time* to noon. A route requested at 06:00 or
at 23:00 is sampled against midday conditions.

**Proposed change.** Once `departure_time` (P0-1) exists, default to the real current
time instead:

```python
ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
```

---

### P2-5 — `total_cost` is inconsistent on the snap-collision path

**Evidence.** When start and destination snap to the same grid node, `services.py`
returns:

```python
total_cost=round(dist * 0.1, 2)
```

That is distance × 0.1, which is a completely different quantity from the D* Lite
path cost returned on the normal path. The same JSON field carries two incompatible
scales depending on an internal branch the client cannot see.

**Proposed change.** Either compute a real single-segment cost via `CostModel`, or
return `null` with `route_status: "unavailable"`. A wrong number is worse than an
absent one, because the frontend has no way to know it should be distrusted.

---

## 8. Proposed new error codes

Additive to §14 of the contract.

| Code | HTTP | Meaning |
| :--- | :--- | :--- |
| `DEPARTURE_TIME_OUT_OF_RANGE` | 400 | Departure time is in the past or beyond forecast horizon |
| `SHIP_PARTICULARS_REQUIRED` | 400 | Neither `imo_number` nor a complete `ship` object supplied |
| `HAZARD_BLOCKING` | 409 | No navigable route exists due to hazardous conditions |

For `SHIP_PARTICULARS_REQUIRED`, please include the missing fields so the frontend can
open the manual-entry form pre-targeted at exactly what is needed:

```jsonc
{
  "error": {
    "code": "SHIP_PARTICULARS_REQUIRED",
    "message": "Ship particulars are required when no IMO number is supplied.",
    "missing_fields": ["draft_m", "cruising_speed_kn"]   // NEW, optional
  }
}
```

---

## 9. Two engine-level notes

These are outside the API contract but affect what the frontend can render. Both come
from reading `naudisha/routing/graph.py`.

### 9.1 — 4-connected grid produces staircase routes

`GeographicGridGraph.DIRECTIONS_4` allows only North, South, East, West movement:

```python
DIRECTIONS_4 = [(1, 0, "North"), (-1, 0, "South"), (0, 1, "East"), (0, -1, "West")]
```

A 4-connected grid cannot express diagonal travel, so any route with both a
north-south and an east-west component comes out as a right-angle staircase. On a map
this reads as broken rather than optimal, and it inflates reported distance by up to
~41% versus the true path on diagonal legs.

**Suggestion:** add the four diagonal offsets to make it 8-connected. The cost model,
D* Lite, and every existing test should be unaffected — the graph layer is already
direction-agnostic, and edge cost is computed from real geographic coordinates rather
than grid steps.

The frontend will additionally render a smoothed curve through the true waypoints
(keeping the real waypoints as markers), but that is cosmetic — it cannot recover
distance accuracy lost to the connectivity constraint.

### 9.2 — No land mask

Every node is created navigable; nothing consults bathymetry or a coastline. A start
or destination on land will route straight through a landmass.

For the MVP the frontend will constrain point-selection to a sea bounding box around
the Arabian Sea demo corridor (18–19°N, 71–72°E) and warn outside it. That is a
guardrail, not a fix — worth flagging as the largest gap between the current demo and
a system that could be described as production-realistic.

---

## 10. Sign-off

Backend: please mark each item and push back on anything you disagree with. If an item
is rejected the frontend will design around the existing contract — we just need to
know which, so we build the right fallback.

| # | Item | Accept / Reject / Discuss | Notes |
| :--- | :--- | :--- | :--- |
| P0-1 | `departure_time` | | |
| P0-2 | Ship particulars + `missing_fields` | | |
| P0-3 | IMO-less flow | | |
| P1-1 | `alerts` array | | |
| P1-2 | `destination` in status/route | | |
| P1-3 | `tracking/start` body | | |
| P1-4 | ISO 8713 IMO validation | | |
| P2-1 | Document `/health` | | |
| P2-2 | `baseline_cost` | | |
| P2-3 | `legs` array | | |
| P2-4 | Default timestamp fix | | |
| P2-5 | Fallback cost consistency | | |
| 9.1 | 8-connected grid | | |
| 9.2 | Land mask | | |

---

## 11. Open questions for backend

Answers to these unblock frontend work that cannot be guessed at:

1. **WebSocket handshake** — does the client send anything on connect (subscribe
   message, auth), or does the server begin pushing immediately?
2. **Heartbeat** — is there a ping/pong frame, and at what interval? The frontend
   needs this to detect a dead connection rather than a quiet one.
3. **Message ordering** — are `route_update` messages guaranteed monotonic by
   `timestamp`? The frontend will apply last-write-wins and discard out-of-order
   messages, which is only safe if timestamps are reliable.
4. **Vessel lookup** — is a real IMO registry or AIS source planned behind
   `POST /api/ships`, or should the frontend assume manual entry is the primary path
   for the MVP?
5. **Update cadence** — roughly how often will the backend push `position_update` and
   re-evaluate the route? This sets the frontend's animation timing and the polling
   interval used when the WebSocket is unavailable.
6. **Tracking scope** — for Flow A (ship already sailing), where does the destination
   come from if the user never planned the voyage in this session?

---

*Frontend will build against the current contract in the meantime, treating every
field above as optional. No backend change is required for frontend work to proceed.*
