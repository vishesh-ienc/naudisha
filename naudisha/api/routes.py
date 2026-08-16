"""
FastAPI route controllers for NauDisha Backend API.
Handles HTTP request decoding, schema validation, dependency injection,
and response serialization according to docs/API_CONTRACT.md.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, status

from naudisha.api.schemas import (
    Coordinate,
    HealthResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
    ShipIdentifyRequest,
    ShipResponse,
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
    Follows docs/API_CONTRACT.md schema conventions.
    """
    result = service.plan_preview_route(
        imo_number=request.imo_number,
        start_lat=request.start.latitude,
        start_lon=request.start.longitude,
        dest_lat=request.destination.latitude,
        dest_lon=request.destination.longitude,
    )

    route_coords = [
        Coordinate(latitude=lat, longitude=lon)
        for lat, lon in result.route
    ]

    return RoutePreviewResponse(
        imo_number=result.imo_number,
        status=result.status,
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
    )
