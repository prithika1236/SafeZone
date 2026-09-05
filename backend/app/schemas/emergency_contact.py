"""Citizen-owned emergency contact request and response schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

ContactName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
PhoneNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{6,30}[0-9]$"),
]
RelationshipLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class EmergencyContactCreate(BaseModel):
    name: ContactName
    phone_number: PhoneNumber
    relationship_label: RelationshipLabel | None = None


class EmergencyContactUpdate(BaseModel):
    name: ContactName | None = None
    phone_number: PhoneNumber | None = None
    relationship_label: RelationshipLabel | None = None


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone_number: str
    relationship_label: str | None
    created_at: datetime
    updated_at: datetime
