"""
Pydantic data schemas and validation models for NauDisha Backend API.
Strictly adheres to docs/API_CONTRACT.md conventions (v2).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self

from naudisha.core.models import ShipProfile


def validate_iso_8713_imo(v: str) -> str:
    """
    Validates a 7-digit IMO number according to ISO 8713.
    Multiplies first 6 digits by weights [7, 6, 5, 4, 3, 2], sums them,
    and checks if sum % 10 equals the 7th digit.
    """
    cleaned = v.strip() if isinstance(v, str) else ""
    if not re.match(r"^\d{7}$", cleaned):
        raise ValueError("IMO number must be exactly 7 digits.")
    weights = (7, 6, 5, 4, 3, 2)
    checksum = sum(int(d) * w for d, w in zip(cleaned[:6], weights)) % 10
    if checksum != int(cleaned[6]):
        raise ValueError("IMO number check digit is invalid (ISO 8713).")
    return cleaned


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


class ShipProfileSchema(BaseModel):
    """
    Vessel static and hydrodynamic characteristics.
    Uses explicit unit suffixes matching API Contract v2 §2.4.
    """
    ship_type: str = Field(..., description="Vessel classification")
    length_m: float = Field(..., gt=0.0, description="Overall length (LOA) in meters")
    beam_m: float = Field(..., gt=0.0, description="Width at widest point in meters")
    draft_m: float = Field(..., gt=0.0, description="Maximum submerged depth in meters")
    cruising_speed_kn: float = Field(..., gt=0.0, description="Design service speed in knots")
    max_speed_kn: float = Field(..., gt=0.0, description="Maximum operational speed in knots")

    @model_validator(mode="after")
    def validate_speeds(self) -> Self:
        if self.max_speed_kn < self.cruising_speed_kn:
            raise ValueError("max_speed_kn cannot be less than cruising_speed_kn.")
        return self

    def to_domain_model(self) -> ShipProfile:
        """Converts API schema to internal core ShipProfile domain model."""
        return ShipProfile(
            ship_type=self.ship_type,
            length=self.length_m,
            beam=self.beam_m,
            draft=self.draft_m,
            cruising_speed=self.cruising_speed_kn,
            maximum_speed=self.max_speed_kn,
        )

    @classmethod
    def from_domain_model(cls, profile: ShipProfile) -> ShipProfileSchema:
        """Creates an API schema instance from internal ShipProfile domain model."""
        return cls(
            ship_type=profile.ship_type,
            length_m=profile.length,
            beam_m=profile.beam,
            draft_m=profile.draft,
            cruising_speed_kn=profile.cruising_speed,
            max_speed_kn=profile.maximum_speed,
        )


DEFAULT_SHIP_PROFILE_SCHEMA = ShipProfileSchema(
    ship_type="Container Vessel (Panamax)",
    length_m=294.0,
    beam_m=32.2,
    draft_m=12.0,
    cruising_speed_kn=18.0,
    max_speed_kn=23.0,
)


class RoutePreviewRequest(BaseModel):
    """
    Request schema for calculating an optimal route preview.
    POST /api/routes/preview
    """
    imo_number: Optional[str] = Field(
        None,
        description="Ship IMO number represented as a 7-digit string (e.g. '1234567')",
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
    departure_time: Optional[str] = Field(
        None,
        description="ISO 8601 UTC departure timestamp",
        examples=["2026-08-20T06:00:00Z"],
    )
    ship: Optional[ShipProfileSchema] = Field(
        None,
        description="Optional vessel characteristics to use for routing cost calculations",
    )

    @field_validator("imo_number")
    @classmethod
    def validate_imo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_iso_8713_imo(v)

    @field_validator("departure_time")
    @classmethod
    def validate_departure_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        try:
            datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError(f"Invalid ISO 8601 UTC departure_time format: {cleaned}") from exc
        return cleaned

    @model_validator(mode="after")
    def validate_imo_or_ship(self) -> Self:
        if self.imo_number is None and self.ship is None:
            raise ValueError("At least one of imo_number or ship must be provided.")
        return self


class RouteLegSchema(BaseModel):
    """
    Per-segment breakdown of a planned route.

    Enables a client to explain why a route was chosen — which legs the current
    assists, where the vessel meets head seas — rather than only drawing a line.
    Every value is produced by the cost model during edge evaluation.
    """
    from_: Coordinate = Field(..., alias="from", description="Segment start coordinate")
    to: Coordinate = Field(..., description="Segment end coordinate")
    distance_nm: float = Field(..., description="Segment great-circle distance in nautical miles")
    travel_time_hours: float = Field(..., description="Estimated time to traverse this segment")
    bearing: float = Field(..., description="True course over this segment in degrees [0, 360)")
    cost: float = Field(..., description="Weighted multi-objective cost of this segment")

    wind_speed_kn: Optional[float] = Field(None, description="Wind speed at segment midpoint, knots")
    wind_direction_deg: Optional[float] = Field(None, description="Direction wind originates from, degrees")
    wave_height_m: Optional[float] = Field(None, description="Significant wave height Hs, metres")
    wave_period_s: Optional[float] = Field(None, description="Peak wave period Tp, seconds")
    current_speed_kn: Optional[float] = Field(None, description="Ocean current speed, knots")
    current_direction_deg: Optional[float] = Field(None, description="Direction current flows towards, degrees")

    relative_wind_dir: Optional[float] = Field(
        None, description="Wind angle relative to course: 0 deg headwind, 180 deg tailwind"
    )
    relative_current_dir: Optional[float] = Field(
        None, description="Current angle relative to course: 0 deg following, 180 deg opposing"
    )
    along_track_current_kn: Optional[float] = Field(
        None, description="Current component along course; positive assists, negative opposes"
    )
    effective_speed_kn: Optional[float] = Field(
        None, description="Speed over ground after current effect, knots"
    )

    time_score: Optional[float] = Field(None, description="Normalised time cost [0 best, 1 worst]")
    fuel_score: Optional[float] = Field(None, description="Normalised fuel cost [0 best, 1 worst]")
    wind_score: Optional[float] = Field(None, description="Normalised wind penalty [0 best, 1 worst]")
    wave_score: Optional[float] = Field(None, description="Normalised wave penalty [0 best, 1 worst]")
    current_score: Optional[float] = Field(None, description="Normalised current penalty [0 best, 1 worst]")
    safety_score: Optional[float] = Field(None, description="Normalised safety margin [0 best, 1 worst]")

    model_config = {"populate_by_name": True}


class RoutePreviewResponse(BaseModel):
    """
    Response schema for route preview calculation.
    POST /api/routes/preview
    """
    imo_number: Optional[str] = Field(None, description="Echoed ship IMO number or null for IMO-less routing")
    status: str = Field("route_ready", description="Route planning status ('route_ready')")
    departure_time: str = Field(..., description="The departure time actually used (ISO 8601 UTC)")
    eta: str = Field(..., description="Estimated time of arrival (ISO 8601 UTC)")
    route: List[Coordinate] = Field(..., description="Ordered list of route waypoints from start to destination")
    distance_nm: float = Field(..., description="Total route distance in nautical miles")
    estimated_time_hours: float = Field(..., description="Estimated voyage transit duration in hours")
    total_cost: float = Field(..., description="Total multi-objective environmental route cost")
    legs: List[RouteLegSchema] = Field(
        default_factory=list,
        description="Per-segment environmental and cost breakdown explaining the route choice",
    )


class ShipIdentifyRequest(BaseModel):
    """Request schema to create or identify a ship."""
    imo_number: str = Field(..., description="Ship IMO number as a 7-digit string")

    @field_validator("imo_number")
    @classmethod
    def validate_imo(cls, v: str) -> str:
        return validate_iso_8713_imo(v)


class ShipResponse(BaseModel):
    """Ship status response schema."""
    imo_number: str
    name: str
    status: str = "underway"  # "underway", "stopped", "unknown"
    position: Optional[Coordinate] = None
    ship: ShipProfileSchema


class TrackingStartRequest(BaseModel):
    """Request schema to begin ship tracking."""
    destination: Coordinate = Field(..., description="Voyage destination coordinates")
    origin: Optional[Coordinate] = Field(
        None,
        description=(
            "Optional starting position. Falls back to the vessel's live AIS position, "
            "then to the demo-corridor default when no AIS fix is available."
        ),
    )
    departure_time: Optional[str] = Field(
        None,
        description="Optional ISO 8601 UTC departure timestamp for environmental sampling",
        examples=["2026-08-20T06:00:00Z"],
    )

    @field_validator("departure_time")
    @classmethod
    def validate_departure_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        try:
            datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError(f"Invalid ISO 8601 UTC departure_time format: {cleaned}") from exc
        return cleaned


class TrackingStartResponse(BaseModel):
    """Response schema for start tracking."""
    imo_number: str
    tracking: bool = True
    message: str = "Ship tracking started"


class TrackingStopResponse(BaseModel):
    """Response schema for stop tracking."""
    imo_number: str
    tracking: bool = False
    message: str = "Ship tracking stopped"


class ShipStatusResponse(BaseModel):
    """Ship status query response schema."""
    imo_number: str
    status: str = "underway"  # "underway", "stopped", "unknown"
    position: Coordinate
    destination: Optional[Coordinate] = None
    timestamp: str


class ShipRouteResponse(BaseModel):
    """Ship current route query response schema."""
    imo_number: str
    route_status: str = "optimal"  # "optimal", "updating", "unavailable"
    destination: Optional[Coordinate] = None
    route: List[Coordinate]
    distance_nm: float
    estimated_time_hours: float
    total_cost: float
    updated_at: str


class ErrorDetail(BaseModel):
    """Standard error detail object adhering to API contract."""
    code: str = Field(..., description="Standardized error code string")
    message: str = Field(..., description="Human-readable error description")


class ErrorResponse(BaseModel):
    """Standard top-level error response envelope."""
    error: ErrorDetail


# Defined after ErrorDetail so the annotation resolves without a forward
# reference — `from __future__ import annotations` defers evaluation, but
# Pydantic resolves field types at class construction.
class PlanJobResponse(BaseModel):
    """
    Response for an asynchronous planning job.

    A cold plan costs 75-85s of live Copernicus queries, which no HTTP client
    should block on. Clients submit a job, then poll until `status` leaves
    "planning".
    """
    job_id: str = Field(..., description="Identifier used to poll for the result")
    status: str = Field(..., description="'planning' | 'ready' | 'failed'")
    elapsed_seconds: float = Field(0.0, description="Seconds since the job was submitted")
    route: Optional[RoutePreviewResponse] = Field(
        None, description="Populated once status is 'ready'"
    )
    error: Optional[ErrorDetail] = Field(
        None, description="Populated once status is 'failed'"
    )


class ReadinessResponse(BaseModel):
    """Readiness probe result — reports whether live providers are usable."""
    status: str = Field(..., description="'ready' or 'degraded'")
    service: str = Field("naudisha-backend", description="Service identifier")
    providers: Dict[str, bool] = Field(
        default_factory=dict, description="Per-provider availability flags"
    )
