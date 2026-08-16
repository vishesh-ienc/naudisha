"""
FastAPI route controllers for NauDisha Backend API.
Handles HTTP request decoding, schema validation, dependency injection,
and response serialization according to docs/API_CONTRACT.md (v2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect, status

from naudisha.api.errors import InvalidIMOError
from naudisha.api.schemas import (
    Coordinate,
    DEFAULT_SHIP_PROFILE_SCHEMA,
    HealthResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
    ShipIdentifyRequest,
    ShipResponse,
    ShipRouteResponse,
    ShipStatusResponse,
    TrackingStartRequest,
    TrackingStartResponse,
    validate_iso_8713_imo,
)
from naudisha.api.services import RoutePlanningService

# -----------------------------------------------------------------------------
# Dependency Injection
# -----------------------------------------------------------------------------

# Singleton default instance (can be overridden per test)
_default_route_service: Optional[RoutePlanningService] = None


def get_route_service() -> RoutePlanningService:
    """Dependency provider for RoutePlanningService."""
    global _default_route_service
    if _default_route_service is None:
        _default_route_service = RoutePlanningService()
    return _default_route_service


# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------

health_router = APIRouter(tags=["Health"])
api_router = APIRouter(prefix="/api", tags=["Routing & Vessels"])
ws_router = APIRouter(tags=["WebSocket"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Backend Health Check",
    description="Returns service status without querying external meteorological providers or routing algorithms.",
)
def get_health() -> HealthResponse:
    """Independent health check verifying backend application availability."""
    return HealthResponse(status="ok", service="naudisha-backend")


@api_router.post(
    "/routes/preview",
    response_model=RoutePreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview Optimal Route",
    description="Calculates the planned optimal marine route between start and destination coordinates.",
)
def preview_route(
    request: RoutePreviewRequest,
    service: RoutePlanningService = Depends(get_route_service),
) -> RoutePreviewResponse:
    """
    Calculates an optimal route for a given IMO vessel and geographic coordinates.
    Follows docs/API_CONTRACT.md (v2) schema conventions.
    """
    ship_profile = request.ship.to_domain_model() if request.ship is not None else None

    result = service.plan_preview_route(
        imo_number=request.imo_number,
        start_lat=request.start.latitude,
        start_lon=request.start.longitude,
        dest_lat=request.destination.latitude,
        dest_lon=request.destination.longitude,
        timestamp=request.departure_time,
        ship_profile=ship_profile,
    )

    route_coords = [
        Coordinate(latitude=lat, longitude=lon)
        for lat, lon in result.route
    ]

    return RoutePreviewResponse(
        imo_number=result.imo_number,
        status=result.status,
        departure_time=result.departure_time,
        eta=result.eta,
        route=route_coords,
        distance_nm=result.distance_nm,
        estimated_time_hours=result.estimated_time_hours,
        total_cost=result.total_cost,
    )


@api_router.post(
    "/ships",
    response_model=ShipResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or Identify Ship",
    description="Identifies a vessel by IMO number for tracking or route planning.",
)
def identify_ship(
    request: ShipIdentifyRequest,
) -> ShipResponse:
    """MVP demo vessel identification endpoint."""
    return ShipResponse(
        imo_number=request.imo_number,
        name="Demo Vessel",
        status="underway",
        position=Coordinate(latitude=18.52, longitude=72.91),
        ship=DEFAULT_SHIP_PROFILE_SCHEMA,
    )


@api_router.post(
    "/ships/{imo_number}/tracking/start",
    response_model=TrackingStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Tracking",
    description="Begins live position tracking and route replanning for the vessel.",
)
def start_tracking(
    request: TrackingStartRequest,
    imo_number: str = Path(..., description="7-digit IMO number"),
) -> TrackingStartResponse:
    """MVP demo tracking start endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    return TrackingStartResponse(
        imo_number=imo_number,
        tracking=True,
        message="Ship tracking started",
    )


@api_router.get(
    "/ships/{imo_number}/status",
    response_model=ShipStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ship Status",
    description="Returns current vessel status, position, and active destination.",
)
def get_ship_status(
    imo_number: str = Path(..., description="7-digit IMO number"),
) -> ShipStatusResponse:
    """MVP demo vessel status query endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ShipStatusResponse(
        imo_number=imo_number,
        status="underway",
        position=Coordinate(latitude=18.58, longitude=72.94),
        destination=Coordinate(latitude=19.07, longitude=72.87),
        timestamp=now_iso,
    )


@api_router.get(
    "/ships/{imo_number}/route",
    response_model=ShipRouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Ship Route",
    description="Returns the currently active optimal route for the tracked vessel.",
)
def get_ship_route(
    imo_number: str = Path(..., description="7-digit IMO number"),
) -> ShipRouteResponse:
    """MVP demo vessel route query endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ShipRouteResponse(
        imo_number=imo_number,
        route_status="optimal",
        destination=Coordinate(latitude=19.07, longitude=72.87),
        route=[
            Coordinate(latitude=18.58, longitude=72.94),
            Coordinate(latitude=18.75, longitude=72.91),
            Coordinate(latitude=19.07, longitude=72.87),
        ],
        distance_nm=110.42,
        estimated_time_hours=6.12,
        total_cost=15.87,
        updated_at=now_iso,
    )


@ws_router.websocket("/ws/ships/{imo_number}")
async def websocket_ship_endpoint(websocket: WebSocket, imo_number: str) -> None:
    """
    WebSocket endpoint for live ship position and route updates.
    Conforms to docs/API_CONTRACT.md §9.
    """
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        while True:
            # Acknowledge connection and wait for disconnect or ping frames
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
