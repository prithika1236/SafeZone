"""Validated crime-incident API contracts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CrimeIncidentStatus


class CrimeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    crime_type: str = Field(min_length=1, max_length=120)
    severity: int = Field(ge=1, le=5)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    occurred_at: datetime
    reported_at: datetime
    ward: str | None = Field(default=None, max_length=120)
    area: str | None = Field(default=None, max_length=180)
    source_reference: str | None = Field(default=None, min_length=1, max_length=160)
    status: CrimeIncidentStatus = CrimeIncidentStatus.REPORTED

    @model_validator(mode="after")
    def validate_times(self) -> "CrimeCreate":
        if self.occurred_at.tzinfo is None or self.reported_at.tzinfo is None:
            raise ValueError("occurred_at and reported_at must include timezone information")
        if self.reported_at < self.occurred_at:
            raise ValueError("reported_at must not be earlier than occurred_at")
        return self


class CrimeUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    crime_type: str | None = Field(default=None, min_length=1, max_length=120)
    severity: int | None = Field(default=None, ge=1, le=5)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    occurred_at: datetime | None = None
    reported_at: datetime | None = None
    ward: str | None = Field(default=None, max_length=120)
    area: str | None = Field(default=None, max_length=180)
    status: CrimeIncidentStatus | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> "CrimeUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        for value in (self.occurred_at, self.reported_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("timestamps must include timezone information")
        return self


class CrimeResponse(BaseModel):
    id: UUID
    crime_type: str
    severity: int
    latitude: float
    longitude: float
    occurred_at: datetime
    reported_at: datetime
    ward: str | None
    area: str | None
    source_reference: str | None
    status: CrimeIncidentStatus
    created_at: datetime
    updated_at: datetime


class CrimePage(BaseModel):
    items: list[CrimeResponse]
    total: int
    limit: int
    offset: int


class CrimeBulkRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class CrimeBulkRejection(BaseModel):
    row: int
    reason: str


class CrimeBulkResult(BaseModel):
    total_rows: int
    accepted: int
    duplicates: list[str]
    rejected: list[CrimeBulkRejection]
