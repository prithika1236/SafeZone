"""Contracts for controlled live-location and device registration operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PoliceLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=10_000)


class PoliceLocationAccepted(BaseModel):
    id: UUID
    recorded_at: datetime
    minimum_interval_seconds: int


class DeviceRegistrationCreate(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    platform: Literal["android", "ios", "web"]


class DeviceRegistrationResponse(BaseModel):
    registered: bool = True

