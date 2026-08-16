"""
NauDisha Backend API Package.
Provides REST endpoints, request/response models, service adapters,
and standard error handlers compliant with docs/API_CONTRACT.md.
"""

from naudisha.api.main import app, create_app
from naudisha.api.schemas import (
    Coordinate,
    HealthResponse,
    RoutePreviewRequest,
    RoutePreviewResponse,
    ShipIdentifyRequest,
    ShipResponse,
    ErrorDetail,
    ErrorResponse,
)
from naudisha.api.services import RoutePlanningService, RoutePlanResult
from naudisha.api.errors import (
    APIException,
    InvalidIMOError,
    InvalidCoordinatesError,
    ShipNotFoundError,
    RouteNotFoundError,
    TrackingUnavailableError,
    EnvironmentUnavailableError,
    InternalError,
)

__all__ = [
    "app",
    "create_app",
    "Coordinate",
    "HealthResponse",
    "RoutePreviewRequest",
    "RoutePreviewResponse",
    "ShipIdentifyRequest",
    "ShipResponse",
    "ErrorDetail",
    "ErrorResponse",
    "RoutePlanningService",
    "RoutePlanResult",
    "APIException",
    "InvalidIMOError",
    "InvalidCoordinatesError",
    "ShipNotFoundError",
    "RouteNotFoundError",
    "TrackingUnavailableError",
    "EnvironmentUnavailableError",
    "InternalError",
]
