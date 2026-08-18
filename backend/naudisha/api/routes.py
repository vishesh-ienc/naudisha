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
    ErrorDetail,
    HealthResponse,
    PlanJobResponse,
    ReadinessResponse,
    RouteLegSchema,
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
    AISTrackPoint,
    AISTrackResponse,
    AISStatsResponse,
    DynamicReplanRequest,
    DynamicReplanResponse,
    HazardInjectionSchema,
    validate_iso_8713_imo,
)
from naudisha.api.planning import planning_manager
from naudisha.api.services import RoutePlanningService
from naudisha.api.tracking import tracking_manager
from naudisha.core.models import ShipProfile
from naudisha.data.vessel_provider import CompositeVesselProvider, VesselProvider

# DEFAULT_ORIGIN is kept only for route planning seed coordinates in tests.
# It MUST NOT be used as a vessel position fallback in any response.
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
        optimization_objective=request.optimization_objective,
    )

    route_coords = [
        Coordinate(latitude=lat, longitude=lon)
        for lat, lon in result.route
    ]

    return _to_preview_response(result)


def _to_preview_response(result) -> RoutePreviewResponse:
    """Maps a RoutePlanResult onto the wire schema, including per-leg detail."""
    return RoutePreviewResponse(
        imo_number=result.imo_number,
        status=result.status,
        departure_time=result.departure_time,
        eta=result.eta,
        route=[Coordinate(latitude=lat, longitude=lon) for lat, lon in result.route],
        distance_nm=result.distance_nm,
        estimated_time_hours=result.estimated_time_hours,
        total_cost=result.total_cost,
        optimization_objective=getattr(result, "optimization_objective", None),
        cost_weights=getattr(result, "cost_weights", None),
        legs=[
            RouteLegSchema(
                **{"from": Coordinate(latitude=leg.from_lat, longitude=leg.from_lon)},
                to=Coordinate(latitude=leg.to_lat, longitude=leg.to_lon),
                distance_nm=leg.distance_nm,
                travel_time_hours=leg.travel_time_hours,
                bearing=leg.bearing,
                cost=leg.cost,
                wind_speed_kn=leg.wind_speed_kn,
                wind_direction_deg=leg.wind_direction_deg,
                wave_height_m=leg.wave_height_m,
                wave_period_s=leg.wave_period_s,
                current_speed_kn=leg.current_speed_kn,
                current_direction_deg=leg.current_direction_deg,
                relative_wind_dir=leg.relative_wind_dir,
                relative_current_dir=leg.relative_current_dir,
                along_track_current_kn=leg.along_track_current_kn,
                effective_speed_kn=leg.effective_speed_kn,
                time_score=leg.time_score,
                fuel_score=leg.fuel_score,
                wind_score=leg.wind_score,
                wave_score=leg.wave_score,
                current_score=leg.current_score,
                safety_score=leg.safety_score,
            )
            for leg in result.legs
        ],
        environment_source=getattr(result, "environment_source", "copernicus_live"),
    )


@api_router.post(
    "/routes/simulate-replan",
    response_model=DynamicReplanResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate Real-Time D* Lite Dynamic Replanning",
    description="Injects a dynamic weather or navigation hazard and executes fast D* Lite incremental path repair.",
)
def simulate_replan(
    request: DynamicReplanRequest,
    service: RoutePlanningService = Depends(get_route_service),
) -> DynamicReplanResponse:
    res = service.simulate_dynamic_replan(
        current_lat=request.current_position.latitude,
        current_lon=request.current_position.longitude,
        dest_lat=request.destination.latitude,
        dest_lon=request.destination.longitude,
        hazard_lat=request.hazard.center.latitude,
        hazard_lon=request.hazard.center.longitude,
        hazard_radius_nm=request.hazard.radius_nm,
        hazard_type=request.hazard.type,
        hazard_severity=request.hazard.severity,
        optimization_objective=request.optimization_objective,
        timestamp=request.departure_time,
    )

    return DynamicReplanResponse(
        new_route=[Coordinate(latitude=lat, longitude=lon) for lat, lon in res["new_route"]],
        previous_route=request.active_route,
        replan_time_ms=res["replan_time_ms"],
        affected_edges_count=res["affected_edges_count"],
        hazard_avoidance_score=res["hazard_avoidance_score"],
        distance_nm=res["distance_nm"],
        estimated_time_hours=res["estimated_time_hours"],
        total_cost=res["total_cost"],
        legs=[
            RouteLegSchema(
                **{"from": Coordinate(latitude=leg.from_lat, longitude=leg.from_lon)},
                to=Coordinate(latitude=leg.to_lat, longitude=leg.to_lon),
                distance_nm=leg.distance_nm,
                travel_time_hours=leg.travel_time_hours,
                bearing=leg.bearing,
                cost=leg.cost,
                wind_speed_kn=leg.wind_speed_kn,
                wind_direction_deg=leg.wind_direction_deg,
                wave_height_m=leg.wave_height_m,
                wave_period_s=leg.wave_period_s,
                current_speed_kn=leg.current_speed_kn,
                current_direction_deg=leg.current_direction_deg,
                relative_wind_dir=leg.relative_wind_dir,
                relative_current_dir=leg.relative_current_dir,
                along_track_current_kn=leg.along_track_current_kn,
                effective_speed_kn=leg.effective_speed_kn,
                time_score=leg.time_score,
                fuel_score=leg.fuel_score,
                wind_score=leg.wind_score,
                wave_score=leg.wave_score,
                current_score=leg.current_score,
                safety_score=leg.safety_score,
            )
            for leg in res["legs"]
        ],
    )


@api_router.post(
    "/routes/plan",
    response_model=PlanJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Asynchronous Route Plan",
    description=(
        "Starts a route planning job and returns immediately. A cold plan costs 75-85s of "
        "live Copernicus queries, so clients poll GET /api/routes/plan/{job_id} "
        "instead of holding an HTTP request open."
    ),
)
def submit_route_plan(
    request: RoutePreviewRequest,
    service: RoutePlanningService = Depends(get_route_service),
    vessel_provider: VesselProvider = Depends(get_vessel_provider),
) -> PlanJobResponse:
    """Queues a plan and returns a job handle. Identical voyages share one job."""
    ship_profile = request.ship.to_domain_model() if request.ship is not None else None

    planning_manager.set_route_service(service)

    signature = planning_manager.signature(
        imo_number=request.imo_number,
        start=(request.start.latitude, request.start.longitude),
        destination=(request.destination.latitude, request.destination.longitude),
        departure_time=request.departure_time,
        optimization_objective=request.optimization_objective,
    )

    job = planning_manager.submit(
        signature,
        profile_resolver=(
            (lambda: _resolve_ship_profile(request, vessel_provider))
            if ship_profile is None and request.imo_number is not None
            else None
        ),
        imo_number=request.imo_number,
        start_lat=request.start.latitude,
        start_lon=request.start.longitude,
        dest_lat=request.destination.latitude,
        dest_lon=request.destination.longitude,
        timestamp=request.departure_time,
        ship_profile=ship_profile,
        optimization_objective=request.optimization_objective,
    )

    return _job_to_response(job)


@api_router.get(
    "/routes/plan/{job_id}",
    response_model=PlanJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll Asynchronous Route Plan",
    description="Returns the current state of a planning job submitted via POST /api/routes/plan.",
)
def get_route_plan(job_id: str = Path(..., description="Job identifier")) -> PlanJobResponse:
    job = planning_manager.get(job_id)
    if job is None:
        raise RouteNotFoundError(f"No planning job found with id '{job_id}'.")
    return _job_to_response(job)


def _job_to_response(job) -> PlanJobResponse:
    return PlanJobResponse(
        job_id=job.job_id,
        status=job.status,
        stage=getattr(job, "stage", "planning"),
        stage_message=getattr(job, "stage_message", None),
        progress_percent=getattr(job, "progress_percent", 0.0),
        elapsed_seconds=round(job.elapsed_seconds, 2),
        route=_to_preview_response(job.result) if job.result is not None else None,
        error=(
            ErrorDetail(code=job.error_code or "INTERNAL_ERROR", message=job.error_message or "Planning failed")
            if job.status == "failed"
            else None
        ),
    )


def _resolve_ship_profile(
    request: RoutePreviewRequest, vessel_provider: VesselProvider
) -> Optional[ShipProfile]:
    """Explicit particulars win; otherwise resolve from IMO, else service default."""
    if request.ship is not None:
        return request.ship.to_domain_model()

    if request.imo_number is not None:
        vessel = vessel_provider.get_vessel_by_imo(request.imo_number)
        if vessel is not None:
            return ShipProfile(
                ship_type=vessel.ship_type,
                length=vessel.length_m,
                beam=vessel.beam_m,
                draft=vessel.draft_m,
                cruising_speed=vessel.cruising_speed_kn,
                maximum_speed=vessel.max_speed_kn,
            )

    return None


@health_router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Reports whether the environmental and vessel providers are configured and usable.",
)
def get_ready(
    service: RoutePlanningService = Depends(get_route_service),
) -> ReadinessResponse:
    """
    Readiness differs from liveness: the process can be up while Copernicus
    credentials are missing, in which case routes still compute but on fallback
    conditions rather than live observations. Clients deserve to know which.
    """
    import os

    providers = {
        "environment_provider": service.environment_provider is not None,
        "copernicus_credentials": bool(
            os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME")
            and os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD")
        ),
        "aisstream_key": bool(os.environ.get("AISSTREAM_API_KEY")),
    }
    all_ready = all(providers.values())

    return ReadinessResponse(
        status="ready" if all_ready else "degraded",
        service="naudisha-backend",
        providers=providers,
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
        is_live_position=vessel.is_live_position,
        position_source=vessel.source if vessel.is_live_position else "static" if position else "none",
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

    # Prefer an explicit origin, then live AIS position. Never fall back to fake coordinates.
    if request.origin is not None:
        origin = (request.origin.latitude, request.origin.longitude)
    elif vessel.position_lat is not None and vessel.position_lon is not None:
        origin = (vessel.position_lat, vessel.position_lon)
    else:
        raise InvalidCoordinatesError(
            "No live AIS position available for this vessel. Please specify an origin coordinate or select a departure port."
        )

    if abs(origin[0] - destination[0]) < 1e-6 and abs(origin[1] - destination[1]) < 1e-6:
        raise InvalidCoordinatesError("Destination must differ from the vessel's origin position.")

    tracking_manager.set_route_service(route_service)
    if hasattr(vessel_provider, "ais_manager"):
        tracking_manager.set_ais_provider(vessel_provider.ais_manager)

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
        is_live = session.position_source == "ais"
        return ShipStatusResponse(
            imo_number=imo_number,
            status=session.status,
            position=Coordinate(latitude=round(session.position[0], 4), longitude=round(session.position[1], 4)),
            destination=Coordinate(
                latitude=round(session.destination[0], 4), longitude=round(session.destination[1], 4)
            ),
            timestamp=session.updated_at,
            is_live_position=is_live,
            position_source=session.position_source,
        )


    # No active session. Report the AIS position if one is known; return null
    # position rather than a fallback coordinate — a null position is honest,
    # a fabricated coordinate is not.
    if vessel.position_lat is not None and vessel.position_lon is not None:
        pos = Coordinate(latitude=vessel.position_lat, longitude=vessel.position_lon)
    else:
        pos = None

    return ShipStatusResponse(
        imo_number=imo_number,
        status=vessel.status,
        position=pos,
        destination=None,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        is_live_position=vessel.is_live_position,
        position_source=vessel.source if vessel.is_live_position else ("static" if pos else "none"),
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


# ---------------------------------------------------------------------------
# AIS Track History
# ---------------------------------------------------------------------------


@api_router.get(
    "/ships/{imo_number}/track",
    response_model=AISTrackResponse,
    summary="AIS observation history for a tracked vessel",
    description=(
        "Returns the historical list of genuine AIS position observations collected "
        "during an active or recently active tracking session. "
        "Only real AIS fixes are included — never simulated dead-reckoning points. "
        "If no tracking session exists or no AIS fixes have been received, "
        "the track list will be empty."
    ),
)
async def get_ais_track(
    imo_number: str = Path(..., description="7-digit IMO number"),
) -> AISTrackResponse:
    try:
        imo_number = validate_iso_8713_imo(imo_number)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session = tracking_manager.get(imo_number)
    if session is None:
        return AISTrackResponse(imo_number=imo_number, track=[])

    track_points = [
        AISTrackPoint(latitude=lat, longitude=lon, timestamp=ts)
        for lat, lon, ts in session.ais_track
    ]
    return AISTrackResponse(imo_number=imo_number, track=track_points)


# ---------------------------------------------------------------------------
# AIS Diagnostics
# ---------------------------------------------------------------------------


@api_router.get(
    "/ais/stats",
    response_model=AISStatsResponse,
    summary="AISStream provider diagnostics",
    description="Returns real-time statistics from the AISStream ingestion pipeline for debugging.",
)
async def get_ais_stats() -> AISStatsResponse:
    """Exposes AISStreamProvider.stats() for operational visibility."""
    try:
        from naudisha.data.aisstream_provider import AISStreamProvider, ChainedAISProvider
        vessel_prov = get_vessel_provider()
        ais_stream = None
        if hasattr(vessel_prov, "ais_manager"):
            mgr = vessel_prov.ais_manager
            ext = getattr(mgr, "external_provider", None)
            if isinstance(ext, ChainedAISProvider):
                for sub in ext.providers:
                    if isinstance(sub, AISStreamProvider):
                        ais_stream = sub
                        break
            elif isinstance(ext, AISStreamProvider):
                ais_stream = ext
        if ais_stream is not None:
            stats = ais_stream.stats()
            return AISStatsResponse(**stats)
    except Exception:
        pass

    return AISStatsResponse(
        enabled=False,
        connected=False,
        messages_seen=0,
        vessels_with_position=0,
        imo_mappings=0,
        last_error="Provider not available",
    )

