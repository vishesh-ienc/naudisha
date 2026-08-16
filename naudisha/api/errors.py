"""
API error exceptions and standardized exception handlers for NauDisha Backend.
Strictly maps domain & validation errors to docs/API_CONTRACT.md structure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("naudisha.api")


# -----------------------------------------------------------------------------
# Domain & API Exceptions
# -----------------------------------------------------------------------------

class APIException(Exception):
    """Base exception class for all NauDisha API-level errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidIMOError(APIException):
    """Raised when an invalid IMO number format is provided."""

    def __init__(self, message: str = "The supplied IMO number is invalid.") -> None:
        super().__init__(
            code="INVALID_IMO",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ShipNotFoundError(APIException):
    """Raised when the requested ship cannot be found."""

    def __init__(self, message: str = "No ship found for the provided IMO number.") -> None:
        super().__init__(
            code="SHIP_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidCoordinatesError(APIException):
    """Raised when start or destination coordinates are out of bounds or invalid."""

    def __init__(self, message: str = "Start or destination coordinates are invalid.") -> None:
        super().__init__(
            code="INVALID_COORDINATES",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class RouteNotFoundError(APIException):
    """Raised when no valid route could be calculated."""

    def __init__(self, message: str = "No valid route could be calculated.") -> None:
        super().__init__(
            code="ROUTE_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TrackingUnavailableError(APIException):
    """Raised when live tracking is currently unavailable."""

    def __init__(self, message: str = "Live tracking is currently unavailable.") -> None:
        super().__init__(
            code="TRACKING_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class EnvironmentUnavailableError(APIException):
    """Raised when meteorological or hydrodynamic data could not be retrieved."""

    def __init__(self, message: str = "Environmental data could not be retrieved.") -> None:
        super().__init__(
            code="ENVIRONMENT_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class InternalError(APIException):
    """Raised for unexpected backend errors."""

    def __init__(self, message: str = "Unexpected backend error.") -> None:
        super().__init__(
            code="INTERNAL_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# -----------------------------------------------------------------------------
# Exception Handlers Registration
# -----------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard JSON error responses matching docs/API_CONTRACT.md."""

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = exc.errors()
        # Derive specific error code if IMO or coordinate field failed
        code = "VALIDATION_ERROR"
        msg_parts = []

        for err in errors:
            loc = err.get("loc", ())
            msg = err.get("msg", "Invalid value")
            field_name = str(loc[-1]) if loc else "input"

            if "imo" in field_name.lower():
                code = "INVALID_IMO"
            elif any(c in field_name.lower() for c in ["latitude", "longitude", "start", "destination"]):
                code = "INVALID_COORDINATES"

            msg_parts.append(f"{field_name}: {msg}")

        combined_message = "; ".join(msg_parts) or "Request validation failed."
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": code,
                    "message": combined_message,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code_map = {
            400: "INVALID_REQUEST",
            404: "NOT_FOUND",
            422: "VALIDATION_ERROR",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled backend error during request processing: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected internal server error occurred.",
                }
            },
        )
