"""
Pydantic data schemas and validation models for NauDisha Backend API.
Strictly adheres to docs/API_CONTRACT.md conventions.
"""

from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Coordinate(BaseModel):
    """Geographic coordinate in decimal degrees."""
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in degrees [-90 to +90]",
        examples=[18.52],
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in degrees [-180 to +180]",
        examples=[72.91],
    )


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field("ok", description="Service health status")
    service: str = Field("naudisha-backend", description="Service identifier name")


class RoutePreviewRequest(BaseModel):
    """
    Request schema for calculating an optimal route preview.
    POST /api/routes/preview
    """
    imo_number: str = Field(
        ...,
        description="Ship IMO number represented as a string (e.g. '1234567')",
        examples=["1234567"],
    )
    start: Coordinate = Field(
        ...,
        description="Origin departure coordinates",
    )
    destination: Coordinate = Field(
        ...,
        description="Target destination coordinates",
    )

    @field_validator("imo_number")
    @classmethod
    def validate_imo(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not cleaned or not re.match(r"^\d{6,8}$", cleaned):
            raise ValueError("IMO number must be a valid numeric string of 6-8 digits (e.g. '1234567').")
        return cleaned


class RoutePreviewResponse(BaseModel):
    """
    Response schema for route preview calculation.
    POST /api/routes/preview
    """
    imo_number: str = Field(..., description="Ship IMO number")
    status: str = Field("route_ready", description="Route planning status ('route_ready', 'optimal')")
    route: List[Coordinate] = Field(..., description="Ordered list of route waypoints from start to destination")
    distance_nm: float = Field(..., description="Total route distance in nautical miles")
    estimated_time_hours: float = Field(..., description="Estimated voyage transit duration in hours")
    total_cost: float = Field(..., description="Total multi-objective environmental route cost")


class ShipIdentifyRequest(BaseModel):
    """Request schema to create or identify a ship."""
    imo_number: str = Field(..., description="Ship IMO number as a string")

    @field_validator("imo_number")
    @classmethod
    def validate_imo(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not cleaned or not re.match(r"^\d{6,8}$", cleaned):
            raise ValueError("IMO number must be a valid numeric string of 6-8 digits (e.g. '1234567').")
        return cleaned


class ShipResponse(BaseModel):
    """Ship status response schema."""
    imo_number: str
    name: str = "Demo Vessel"
    status: str = "underway"  # "underway", "stopped", "unknown"
    position: Coordinate


class ErrorDetail(BaseModel):
    """Standard error detail object adhering to API contract."""
    code: str = Field(..., description="Standardized error code string")
    message: str = Field(..., description="Human-readable error description")


class ErrorResponse(BaseModel):
    """Standard top-level error response envelope."""
    error: ErrorDetail
