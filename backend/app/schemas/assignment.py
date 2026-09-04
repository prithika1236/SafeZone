"""Patrol assignment request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AssignmentStatus
from app.schemas.location import Coordinate


class AutomaticAssignmentRequest(BaseModel):
    optimization_run_id: UUID


class ManualAssignmentOverride(BaseModel):
    patrol_unit_id: UUID
    police_officer_id: UUID
    prp_location_id: UUID | None = None


class AssignmentResponse(BaseModel):
    id: UUID
    patrol_unit_id: UUID
    police_officer_id: UUID
    prp_location_id: UUID
    prp_location: Coordinate
    shift_start: datetime
    shift_end: datetime
    status: AssignmentStatus
    assigned_at: datetime
    updated_at: datetime
    straight_line_distance_meters: float | None = None


class AssignmentBatchResponse(BaseModel):
    assignments: tuple[AssignmentResponse, ...]
    unassigned_prp_ids: tuple[UUID, ...]


class AssignmentList(BaseModel):
    items: tuple[AssignmentResponse, ...]
    total: int = Field(ge=0)
