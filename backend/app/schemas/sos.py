"""Privacy-scoped SOS request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import SOSStatus
from app.schemas.location import Coordinate


class SOSCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CitizenSOSResponse(BaseModel):
    id: UUID
    status: SOSStatus
    created_at: datetime
    updated_at: datetime
    patrol_assigned: bool
    approximate_responder_distance_meters: int | None = None
    estimated_duration_seconds: int | None = None
    accepted_at: datetime | None = None
    en_route_at: datetime | None = None
    arrived_at: datetime | None = None
    resolved_at: datetime | None = None
    cancelled_at: datetime | None = None


class PoliceSOSResponse(BaseModel):
    id: UUID
    status: SOSStatus
    emergency_location: Coordinate
    created_at: datetime
    updated_at: datetime
    responder_distance_meters: float | None = None
    estimated_duration_seconds: float | None = None
    distance_source: str | None = None
    accepted_at: datetime | None = None
    en_route_at: datetime | None = None
    arrived_at: datetime | None = None
    resolved_at: datetime | None = None


class SOSList(BaseModel):
    items: tuple[PoliceSOSResponse, ...]
