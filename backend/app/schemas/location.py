"""Shared validated geospatial and privacy-scoped map contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CrimeIncidentStatus, PatrolUnitStatus


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BoundingBox(BaseModel):
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def validate_order(self) -> "BoundingBox":
        if self.south >= self.north:
            raise ValueError("south must be below north")
        if self.west >= self.east:
            raise ValueError("west must be left of east; antimeridian boxes are not supported")
        return self


class IncidentMapDTO(BaseModel):
    """Incident map fields safe for authorized administrative/police maps."""

    id: UUID
    crime_type: str
    severity: int
    location: Coordinate
    occurred_at: datetime
    status: CrimeIncidentStatus
    distance_meters: float | None = None


class OperationalPatrolMapDTO(BaseModel):
    """Restricted operational patrol fields; never serialize this to citizens."""

    patrol_unit_id: UUID
    unit_identifier: str
    display_name: str | None
    status: PatrolUnitStatus
    location: Coordinate
    recorded_at: datetime
    distance_meters: float | None = None


class RouteEstimate(BaseModel):
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    provider: str
