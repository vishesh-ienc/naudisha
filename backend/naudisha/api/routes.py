"""
FastAPI route controllers for NauDisha Backend API.
Handles HTTP request decoding, schema validation, dependency injection,
and response serialization according to docs/API_CONTRACT.md (v2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect, status

from naudisha.api.errors import InvalidIMOError, ShipNotFoundError
from naudisha.api.schemas import (
    Coordinate,
    DEFAULT_SHIP_PROFILE_SCHEMA,
    HealthResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
    ShipIdentifyRequest,
    ShipResponse,
    ShipProfileSchema,
    ShipRouteResponse,
    ShipStatusResponse,
    TrackingStartRequest,
    TrackingStartResponse,
    validate_iso_8713_imo,
)
from naudisha.api.services import RoutePlanningService
from naudisha.core.models import ShipProfile
from naudisha.data.vessel_provider import CompositeVesselProvider, VesselProvider

# -----------------------------------------------------------------------------
# Dependency Injection
# -----------------------------------------------------------------------------

# Singleton default instances (can be overridden per test)
_default_route_service: Optional[RoutePlanningService] = None
_default_vessel_provider: Optional[VesselProvider] = None


def get_route_service() -> RoutePlanningService:
    """Dependency provider for RoutePlanningService."""
    global _default_route_service
    if _default_route_service is None:
        _default_route_service = RoutePlanningService()
    return _default_route_service


def get_vessel_provider() -> VesselProvider:
    """Dependency provider for VesselProvider."""
    global _default_vessel_provider
    if _default_vessel_provider is None:
        _default_vessel_provider = CompositeVesselProvider()
    return _default_vessel_provider


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
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> RoutePreviewResponse:
    """
    Calculates an optimal route for a given IMO vessel and geographic coordinates.
    Follows docs/API_CONTRACT.md (v2) schema conventions.
    """
    ship_profile: Optional[ShipProfile] = None

    if request.ship is not None:
        ship_profile = request.ship.to_domain_model()
    elif request.imo_number is not None:
        vessel = vessel_provider.get_vessel_by_imo(request.imo_number)
        if vessel is not None:
            ship_profile = ShipProfile(
                ship_type=vessel.ship_type,
                length=vessel.length_m,
                beam=vessel.beam_m,
                draft=vessel.draft_m,
                cruising_speed=vessel.cruising_speed_kn,
                maximum_speed=vessel.max_speed_kn,
            )
        else:
            ship_profile = None  # Falls back to service default ship profile

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
    description="Identifies a vessel by IMO number using real maritime data.",
)
def identify_ship(
    request: ShipIdentifyRequest,
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> ShipResponse:
    """Real vessel identification endpoint querying maritime records."""
    vessel = vessel_provider.get_vessel_by_imo(request.imo_number)
    if vessel is None:
        raise ShipNotFoundError(f"No ship found for IMO number '{request.imo_number}'.")

    position = (
        Coordinate(latitude=vessel.position_lat, longitude=vessel.position_lon)
        if vessel.position_lat is not None and vessel.position_lon is not None
        else None
    )

    ship_profile = ShipProfileSchema(
        ship_type=vessel.ship_type,
        length_m=vessel.length_m,
        beam_m=vessel.beam_m,
        draft_m=vessel.draft_m,
        cruising_speed_kn=vessel.cruising_speed_kn,
        max_speed_kn=vessel.max_speed_kn,
    )

    return ShipResponse(
        imo_number=vessel.imo_number,
        name=vessel.name,
        status=vessel.status,
        position=position,
        ship=ship_profile,
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
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> TrackingStartResponse:
    """MVP demo tracking start endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    vessel = vessel_provider.get_vessel_by_imo(imo_number)
    if vessel is None:
        raise ShipNotFoundError(f"No ship found for IMO number '{imo_number}'.")

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
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> ShipStatusResponse:
    """MVP demo vessel status query endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    vessel = vessel_provider.get_vessel_by_imo(imo_number)
    if vessel is None:
        raise ShipNotFoundError(f"No ship found for IMO number '{imo_number}'.")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pos_lat = vessel.position_lat if vessel.position_lat is not None else 18.58
    pos_lon = vessel.position_lon if vessel.position_lon is not None else 72.94

    return ShipStatusResponse(
        imo_number=imo_number,
        status=vessel.status,
        position=Coordinate(latitude=pos_lat, longitude=pos_lon),
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
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> ShipRouteResponse:
    """MVP demo vessel route query endpoint."""
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc

    vessel = vessel_provider.get_vessel_by_imo(imo_number)
    if vessel is None:
        raise ShipNotFoundError(f"No ship found for IMO number '{imo_number}'.")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pos_lat = vessel.position_lat if vessel.position_lat is not None else 18.58
    pos_lon = vessel.position_lon if vessel.position_lon is not None else 72.94

    return ShipRouteResponse(
        imo_number=imo_number,
        route_status="optimal",
        destination=Coordinate(latitude=19.07, longitude=72.87),
        route=[
            Coordinate(latitude=pos_lat, longitude=pos_lon),
            Coordinate(latitude=round(pos_lat + 0.17, 2), longitude=round(pos_lon - 0.03, 2)),
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
