# NauDisha — MVP API Contract

## 1. Purpose

This document defines the contract between the NauDisha frontend and backend.

Both frontend and backend MUST follow this document.

The frontend must never assume or invent fields that are not defined here.

The backend must return the structures defined here.

---

# 2. Base URL

Development:

http://localhost:8000

All endpoints below are relative to the backend base URL.

Example:

POST http://localhost:8000/api/routes/preview

---

# 3. Data Conventions

## Coordinates

Always use:

{
  "latitude": number,
  "longitude": number
}

Latitude:

-90 to +90

Longitude:

-180 to +180

## Timestamp

Use ISO-8601 UTC timestamps.

Example:

"2026-08-16T06:30:00Z"

## IMO Number

Represent IMO numbers as strings.

Example:

"1234567"

Do NOT represent IMO numbers as integers.

---

# 4. Create / Identify Ship

## POST /api/ships

Used when the user enters an IMO number.

### Request

{
  "imo_number": "1234567"
}

### Response

{
  "imo_number": "1234567",
  "name": "Demo Vessel",
  "status": "underway",
  "position": {
    "latitude": 18.52,
    "longitude": 72.91
  }
}

### Possible status values

- "underway"
- "stopped"
- "unknown"

---

# 5. Preview Optimal Route

## POST /api/routes/preview

Used when the user wants to calculate an optimal route before tracking begins.

### Request

{
  "imo_number": "1234567",
  "start": {
    "latitude": 18.52,
    "longitude": 72.91
  },
  "destination": {
    "latitude": 19.07,
    "longitude": 72.87
  }
}

### Response

{
  "imo_number": "1234567",
  "status": "route_ready",
  "route": [
    {
      "latitude": 18.52,
      "longitude": 72.91
    },
    {
      "latitude": 18.65,
      "longitude": 72.95
    },
    {
      "latitude": 18.82,
      "longitude": 72.92
    },
    {
      "latitude": 19.07,
      "longitude": 72.87
    }
  ],
  "distance_nm": 117.14,
  "estimated_time_hours": 6.51,
  "total_cost": 16.31
}

---

# 6. Start Tracking

## POST /api/ships/{imo_number}/tracking/start

Example:

POST /api/ships/1234567/tracking/start

### Response

{
  "imo_number": "1234567",
  "tracking": true,
  "message": "Ship tracking started"
}

---

# 7. Get Ship Status

## GET /api/ships/{imo_number}/status

### Response

{
  "imo_number": "1234567",
  "status": "underway",
  "position": {
    "latitude": 18.58,
    "longitude": 72.94
  },
  "timestamp": "2026-08-16T06:30:00Z"
}

---

# 8. Get Current Route

## GET /api/ships/{imo_number}/route

### Response

{
  "imo_number": "1234567",
  "route_status": "optimal",
  "route": [
    {
      "latitude": 18.58,
      "longitude": 72.94
    },
    {
      "latitude": 18.75,
      "longitude": 72.91
    },
    {
      "latitude": 19.07,
      "longitude": 72.87
    }
  ],
  "distance_nm": 110.42,
  "estimated_time_hours": 6.12,
  "total_cost": 15.87,
  "updated_at": "2026-08-16T06:30:00Z"
}

---

# 9. Live Updates

## WebSocket

/ws/ships/{imo_number}

Example:

ws://localhost:8000/ws/ships/1234567

The WebSocket is used for live ship position and route updates.

---

# 10. Route Update Message

### Message

{
  "type": "route_update",
  "timestamp": "2026-08-16T06:35:00Z",
  "position": {
    "latitude": 18.61,
    "longitude": 72.95
  },
  "route": [
    {
      "latitude": 18.61,
      "longitude": 72.95
    },
    {
      "latitude": 18.82,
      "longitude": 72.88
    },
    {
      "latitude": 19.07,
      "longitude": 72.87
    }
  ],
  "distance_nm": 108.32,
  "estimated_time_hours": 6.01,
  "total_cost": 15.42,
  "reason": "environment_changed"
}

---

# 11. Position Update Message

The backend may send position-only updates.

{
  "type": "position_update",
  "timestamp": "2026-08-16T06:40:00Z",
  "position": {
    "latitude": 18.65,
    "longitude": 72.96
  }
}

---

# 12. Route Status

Possible values:

- "optimal"
- "updating"
- "unavailable"

---

# 13. Error Format

All API errors should follow the same structure.

{
  "error": {
    "code": "SHIP_NOT_FOUND",
    "message": "No ship found for the provided IMO number."
  }
}

---

# 14. Error Codes

## INVALID_IMO

The supplied IMO number is invalid.

## SHIP_NOT_FOUND

The requested ship could not be found.

## INVALID_COORDINATES

Start or destination coordinates are invalid.

## ROUTE_NOT_FOUND

No valid route could be calculated.

## TRACKING_UNAVAILABLE

Live tracking is currently unavailable.

## ENVIRONMENT_UNAVAILABLE

Environmental data could not be retrieved.

## INTERNAL_ERROR

Unexpected backend error.

---

# 15. Frontend / Backend Responsibility

## Frontend

Responsible for:

- Collecting user input
- Validating basic input format
- Calling APIs
- Displaying ship information
- Displaying routes
- Displaying route statistics
- Displaying tracking information
- Displaying errors/loading states

## Backend

Responsible for:

- Ship lookup/tracking
- Environmental data
- Route generation
- Cost calculation
- D* Lite
- Dynamic replanning
- Data validation
- API error handling

---

# 16. Important Rule

The frontend must NEVER:

- Call Copernicus directly
- Call Open-Meteo directly
- Calculate D* Lite routes
- Calculate route costs
- Reimplement environmental scoring
- Invent route data

The backend is the single source of truth for routing.

---

# 17. MVP Endpoint Summary

POST   /api/ships

POST   /api/routes/preview

POST   /api/ships/{imo_number}/tracking/start

GET    /api/ships/{imo_number}/status

GET    /api/ships/{imo_number}/route

WS     /ws/ships/{imo_number}

These endpoints form the initial NauDisha MVP API.

Additional endpoints should only be added when a real MVP requirement needs them.
