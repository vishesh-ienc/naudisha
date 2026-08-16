# NauDisha — Frontend Development Workflow

## 1. What is NauDisha?

NauDisha is a dynamic marine route-planning system.

The user identifies a ship and its voyage. NauDisha uses the ship's position and live environmental conditions such as:

- Ocean currents
- Waves
- Wind

to calculate an optimal marine route.

The backend uses the existing NauDisha routing engine and D* Lite to continuously find an efficient route as environmental conditions change.

The frontend is responsible for presenting this information clearly on a map.

The frontend MUST NOT implement routing mathematics or D* Lite logic.

---

# 2. Overall Application Flow

User
↓
Frontend
↓
Backend API
↓
Ship / Environmental Data
↓
NauDisha Routing Engine
↓
D* Lite
↓
Optimal Route
↓
Backend API
↓
Frontend Map
↓
User

For live tracking:

Ship Position / Environment Changes
↓
Backend
↓
D* Lite Replanning
↓
Updated Route
↓
Frontend

---

# 3. Current MVP Goal

The MVP should demonstrate:

1. User identifies a ship using its IMO number.
2. User can either:
   - Track a ship that is already sailing, OR
   - Plan a voyage before the ship starts.
3. User can provide a start and destination for a planned voyage.
4. Frontend displays the ship/start position and destination on a map.
5. Backend calculates an optimal route.
6. Frontend displays the optimal route.
7. Frontend displays basic route information:
   - Distance
   - Estimated travel time
   - Route cost
8. During tracking, the ship position can be simulated for the demo.
9. Environmental changes can cause the backend to calculate a new route.
10. Frontend displays the updated route.

Do NOT build unnecessary features outside this scope.

---

# 4. User Flow

## Flow A — Ship Already Sailing

User opens NauDisha.

↓

Selects:

"Ship Already Sailing"

↓

Enters:

IMO Number

↓

Clicks:

"Track Ship"

↓

Frontend requests:

GET /api/ships/{imo_number}/status

↓

Backend returns current ship information.

↓

Frontend displays:

- Ship position
- Ship status
- Current route
- Destination
- Route statistics

↓

Tracking continues.

---

# 5. Flow B — Ship Has Not Started

User selects:

"Plan a Voyage"

↓

Enters:

IMO Number

↓

Selects:

Start location

↓

Selects:

Destination

↓

Clicks:

"Preview Optimal Route"

↓

Frontend sends:

POST /api/routes/preview

↓

Backend calculates the optimal route.

↓

Frontend displays:

- Start
- Destination
- Optimal route
- Distance
- Estimated travel time
- Route cost

↓

User can select:

"Start Tracking"

---

# 6. Frontend Development Phases

## Phase 1 — Project Setup

Create the basic frontend structure.

Expected structure:

src/
├── components/
├── pages/
├── services/
├── hooks/
├── map/
├── types/
└── assets/

Create:

- Application layout
- Routing
- Navbar/header
- Main content area
- Basic reusable UI components

Do not implement backend logic here.

---

# Phase 2 — Ship Selection Screen

Create the initial screen.

The user should choose:

### Ship Already Sailing

OR

### Plan a Voyage

Create the IMO input component.

IMO must be validated on the frontend for basic formatting before sending to the backend.

Do not attempt to determine whether an IMO actually exists in the frontend.

The backend is responsible for that.

---

# Phase 3 — Voyage Input

For "Plan a Voyage", create:

### IMO Number

Text input.

### Start

Allow the user to:

- Search/select a location, OR
- Select a point on the map.

### Destination

Allow the user to:

- Search/select a location, OR
- Select a point on the map.

The frontend should store coordinates as:

{
  "latitude": number,
  "longitude": number
}

Do not send human-readable location names as the primary routing input.

---

# Phase 4 — Main Map

Create the primary map interface.

The map should support:

- Ship marker
- Start marker
- Destination marker
- Optimal route polyline
- Updated route polyline
- Basic zoom/pan controls

The frontend should receive route coordinates from the backend.

The frontend must NOT calculate routes itself.

---

# Phase 5 — Ship Information Panel

Display:

- IMO number
- Ship name if available
- Ship status
- Current latitude
- Current longitude
- Destination
- Tracking status

Keep the panel simple for MVP.

---

# Phase 6 — Route Preview

When the user requests a route:

Call:

POST /api/routes/preview

Display:

- Route on map
- Distance
- Estimated travel time
- Total route cost

Show a loading state while the request is running.

Show a clear error if route generation fails.

---

# Phase 7 — Live Tracking UI

Create a tracking interface.

Display:

- Current ship position
- Ship status
- Current route
- Destination
- ETA
- Route status

For the MVP demo, ship movement may be simulated.

The simulation must be clearly treated as demo data.

---

# Phase 8 — Dynamic Route Updates

When the backend sends a new route:

1. Update ship position.
2. Replace/update the route on the map.
3. Update route statistics.
4. Show a notification:

"Route Updated"

The frontend should NOT determine why the route changed.

If the backend provides a reason, display it.

Example:

"Environmental conditions changed."

---

# Phase 9 — API Integration

All API calls MUST be isolated in:

src/services/

Do NOT put fetch/axios calls throughout UI components.

Create functions such as:

- create/identify ship
- preview route
- start tracking
- get ship status
- get current route

The API implementation MUST follow:

docs/API_CONTRACT.md

Do not invent different request or response formats.

---

# Phase 10 — Mock Data

Frontend development must not wait for the backend.

Before backend endpoints are available:

Use mock responses matching the API contract exactly.

Example:

{
  "distance_nm": 117.14,
  "estimated_time_hours": 6.51,
  "total_cost": 16.31
}

When the backend becomes available, replace the mock service with the real API.

Do NOT redesign the UI around a different JSON structure.

---

# Phase 11 — Error & Loading States

Every API-driven feature must handle:

- Loading
- Success
- Invalid IMO
- Ship not found
- Invalid coordinates
- Route unavailable
- Tracking unavailable
- Network failure
- Backend failure

Never leave the UI frozen without feedback.

---

# Phase 12 — MVP Demo Mode

Create a simple demo mode.

Demo mode may simulate:

- Ship movement
- Ship status
- Environmental changes

The demo must clearly indicate when data is simulated.

Example:

"DEMO MODE"

The routing result itself should still use the actual NauDisha routing engine where available.

---

# 7. Frontend Responsibilities

Frontend DOES:

- User input
- Input validation
- Map rendering
- Ship visualization
- Route visualization
- API communication
- Loading states
- Error states
- Route statistics
- Tracking UI
- Route update visualization

Frontend DOES NOT:

- Implement D* Lite
- Calculate route costs
- Calculate environmental effects
- Query Copernicus directly
- Query Open-Meteo directly
- Implement ship-routing algorithms
- Modify routing logic

All such logic belongs to the backend.

---

# 8. Development Rules

1. Follow API_CONTRACT.md exactly.
2. Use mock data until backend endpoints are ready.
3. Keep API calls inside services/.
4. Do not hardcode routing results into UI components.
5. Do not modify backend files.
6. Do not modify D* Lite.
7. Keep commits small and feature-focused.
8. Test each UI feature before opening a PR.
9. Pull latest main before starting major work.
10. Open a Pull Request when a feature is complete.

---

# 9. Recommended Frontend Task Order

1. Project setup
2. Application layout
3. Ship selection screen
4. IMO input
5. Start/destination selection
6. Map
7. Ship information panel
8. Route visualization
9. Route statistics
10. Tracking interface
11. Mock API service
12. Loading/error handling
13. Dynamic route updates
14. Demo mode
15. Real API integration
16. Final UI polish

---

# 10. Definition of Done

Frontend MVP is complete when a user can:

1. Open NauDisha.
2. Enter an IMO number.
3. Choose tracking or voyage planning.
4. Enter/select start and destination when required.
5. See the ship/location on the map.
6. Request an optimal route.
7. See the route on the map.
8. See distance, ETA and cost.
9. Start tracking.
10. See the ship move in demo mode.
11. See the route update when the backend provides a new route.
12. Understand errors and loading states clearly.

The frontend should feel like one complete application rather than a collection of disconnected screens.
