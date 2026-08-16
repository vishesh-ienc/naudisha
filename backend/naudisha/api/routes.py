"""
FastAPI route controllers for NauDisha Backend API.
Handles HTTP request decoding, schema validation, dependency injection,
and response serialization according to docs/API_CONTRACT.md (v2).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect, status

logger = logging.getLogger("naudisha.api.routes")

from naudisha.api.errors import (
    InvalidCoordinatesError,
    InvalidIMOError,
    RouteNotFoundError,
    ShipNotFoundError,
    TrackingUnavailableError,
)
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
    TrackingStopResponse,
    validate_iso_8713_imo,
)
from naudisha.api.services import RoutePlanningService
from naudisha.api.tracking import tracking_manager
from naudisha.core.models import ShipProfile
from naudisha.data.vessel_provider import CompositeVesselProvider, VesselProvider

# Fallback origin used when a vessel has no AIS position and the caller supplied
# none. Open water on the Mumbai approaches — the corridor the routing engine is
# verified against — rather than a coastal point that would route through land.
DEFAULT_ORIGIN = (18.52, 72.55)

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


def _require_valid_imo(imo_number: str) -> str:
    """Validates a path-parameter IMO, translating to the contract error code."""
    try:
        return validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        raise InvalidIMOError(str(exc)) from exc


def _resolve_vessel(vessel_provider: VesselProvider, imo_number: str):
    vessel = vessel_provider.get_vessel_by_imo(imo_number)
    if vessel is None:
        raise ShipNotFoundError(f"No ship found for IMO number '{imo_number}'.")
    return vessel


def _vessel_profile(vessel) -> ShipProfile:
    return ShipProfile(
        ship_type=vessel.ship_type,
        length=vessel.length_m,
        beam=vessel.beam_m,
        draft=vessel.draft_m,
        cruising_speed=vessel.cruising_speed_kn,
        maximum_speed=vessel.max_speed_kn,
    )


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
    route_service: RoutePlanningService = Depends(get_route_service),
) -> TrackingStartResponse:
    """
    Opens a tracking session and schedules its route plan.

    Returns immediately rather than waiting for the plan: a cold route costs
    roughly two minutes of live Copernicus queries, which no client should block
    on. The session reports `route_status: "updating"` until the plan lands, then
    pushes a `route_update` over the WebSocket (contract §13.2).
    """
    _require_valid_imo(imo_number)
    vessel = _resolve_vessel(vessel_provider, imo_number)

    destination = (request.destination.latitude, request.destination.longitude)

    # Prefer an explicit origin, then live AIS, then the demo-corridor default.
    if request.origin is not None:
        origin = (request.origin.latitude, request.origin.longitude)
    elif vessel.position_lat is not None and vessel.position_lon is not None:
        origin = (vessel.position_lat, vessel.position_lon)
    else:
        origin = DEFAULT_ORIGIN

    if abs(origin[0] - destination[0]) < 1e-6 and abs(origin[1] - destination[1]) < 1e-6:
        raise InvalidCoordinatesError("Destination must differ from the vessel's origin position.")

    tracking_manager.set_route_service(route_service)

    try:
        tracking_manager.start(
            imo_number=imo_number,
            origin=origin,
            destination=destination,
            ship_profile=_vessel_profile(vessel),
            departure_time=request.departure_time,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a contract error
        raise TrackingUnavailableError(f"Could not start tracking session: {exc}") from exc

    return TrackingStartResponse(
        imo_number=imo_number,
        tracking=True,
        message="Ship tracking started",
    )


@api_router.post(
    "/ships/{imo_number}/tracking/stop",
    response_model=TrackingStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop Tracking",
    description="Terminates the active tracking session for the vessel.",
)
def stop_tracking(
    imo_number: str = Path(..., description="7-digit IMO number"),
) -> TrackingStopResponse:
    """Ends a tracking session. Idempotent — stopping an unknown session is not an error."""
    _require_valid_imo(imo_number)
    existed = tracking_manager.stop(imo_number)

    return TrackingStopResponse(
        imo_number=imo_number,
        tracking=False,
        message="Ship tracking stopped" if existed else "No active tracking session",
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
    """
    Current vessel status and position.

    When a tracking session is active this reports the live simulated position,
    so polling reflects real movement even with no WebSocket attached. Otherwise
    it falls back to the vessel's last known AIS position.
    """
    _require_valid_imo(imo_number)
    vessel = _resolve_vessel(vessel_provider, imo_number)

    session = tracking_manager.get(imo_number)
    if session is not None:
        return ShipStatusResponse(
            imo_number=imo_number,
            status=session.status,
            position=Coordinate(latitude=round(session.position[0], 4), longitude=round(session.position[1], 4)),
            destination=Coordinate(
                latitude=round(session.destination[0], 4), longitude=round(session.destination[1], 4)
            ),
            timestamp=session.updated_at,
        )

    # No active session. Report the AIS position if one is known; the contract
    # requires a non-null position here, so fall back to the demo corridor
    # origin rather than fabricating a plausible-looking coastal fix.
    pos_lat = vessel.position_lat if vessel.position_lat is not None else DEFAULT_ORIGIN[0]
    pos_lon = vessel.position_lon if vessel.position_lon is not None else DEFAULT_ORIGIN[1]

    return ShipStatusResponse(
        imo_number=imo_number,
        status=vessel.status,
        position=Coordinate(latitude=pos_lat, longitude=pos_lon),
        destination=None,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    """
    The vessel's current optimal route, from its present position to the destination.

    Requires an active tracking session — a route only exists once a voyage has
    been started via §6. Consumed waypoints are dropped so the returned path
    always begins at the vessel's current position (contract §8).
    """
    _require_valid_imo(imo_number)
    _resolve_vessel(vessel_provider, imo_number)

    session = tracking_manager.get(imo_number)
    if session is None:
        raise RouteNotFoundError(
            f"No active route for IMO '{imo_number}'. Start tracking first via "
            f"POST /api/ships/{imo_number}/tracking/start."
        )

    payload = session.snapshot_route_payload()

    return ShipRouteResponse(
        imo_number=imo_number,
        route_status=session.route_status,
        destination=Coordinate(
            latitude=round(session.destination[0], 4), longitude=round(session.destination[1], 4)
        ),
        route=[Coordinate(latitude=p["latitude"], longitude=p["longitude"]) for p in payload["route"]],
        distance_nm=payload["distance_nm"],
        estimated_time_hours=payload["estimated_time_hours"],
        total_cost=payload["total_cost"],
        updated_at=session.updated_at,
    )


@ws_router.websocket("/ws/ships/{imo_number}")
async def websocket_ship_endpoint(websocket: WebSocket, imo_number: str) -> None:
    """
    Live position and route updates for a tracked vessel (contract §9-§11).

    The server pushes as soon as the connection is accepted; no subscribe message
    is required. Two concurrent tasks run per connection: one draining the
    session's broadcast queue to the client, one reading from the client so a
    disconnect is noticed promptly rather than only on the next push.
    """
    try:
        validate_iso_8713_imo(imo_number)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    queue = tracking_manager.subscribe(imo_number)

    async def pump_outbound() -> None:
        # Send the current state immediately, so a client that connects between
        # ticks is not left with a blank screen until the next one.
        session = tracking_manager.get(imo_number)
        if session is not None and session.route:
            payload = session.snapshot_route_payload()
            await websocket.send_json(
                {
                    "type": "route_update",
                    "timestamp": session.updated_at,
                    "position": {
                        "latitude": round(session.position[0], 4),
                        "longitude": round(session.position[1], 4),
                    },
                    **payload,
                    "reason": "forecast_refresh",
                }
            )

        while True:
            message = await queue.get()
            await websocket.send_json(message)

    async def watch_inbound() -> None:
        # The contract defines no client messages; anything received is ignored.
        # This exists purely to observe the disconnect.
        while True:
            await websocket.receive_text()

    outbound = asyncio.create_task(pump_outbound())
    inbound = asyncio.create_task(watch_inbound())

    try:
        done, pending = await asyncio.wait({outbound, inbound}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        # Surface a genuine failure in the outbound pump rather than swallowing it.
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - a broken socket must not take down the app
        logger.debug("WebSocket closed for IMO %s", imo_number, exc_info=True)
    finally:
        outbound.cancel()
        inbound.cancel()
        tracking_manager.unsubscribe(imo_number, queue)
