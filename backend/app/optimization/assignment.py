"""Transparent deterministic patrol-to-PRP allocation primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.location import Coordinate
from app.services.location_service import geodesic_distance_meters


class AssignmentResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    patrol_unit_id: str
    police_officer_id: str
    start_location: Coordinate | None = None
    is_available: bool = True


class AssignmentTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    prp_location_id: str
    location: Coordinate
    risk_score: float = Field(ge=0)


class ProposedAssignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    patrol_unit_id: str
    police_officer_id: str
    prp_location_id: str
    straight_line_distance_meters: float | None


class UnassignedTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    prp_location_id: str
    reason: str


class AssignmentPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    assignments: tuple[ProposedAssignment, ...]
    unassigned: tuple[UnassignedTarget, ...]
    strategy: str = "risk-priority-nearest-v1"


def create_assignment_plan(
    resources: list[AssignmentResource], targets: list[AssignmentTarget]
) -> AssignmentPlan:
    """Allocate each eligible resource once, prioritizing high-risk PRPs then proximity."""
    resource_keys = [(item.patrol_unit_id, item.police_officer_id) for item in resources]
    if len(resource_keys) != len(set(resource_keys)):
        raise ValueError("patrol/officer resource pairs must be unique")
    target_ids = [item.prp_location_id for item in targets]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("PRP target IDs must be unique")

    available = {
        (item.patrol_unit_id, item.police_officer_id): item
        for item in resources
        if item.is_available
    }
    assignments: list[ProposedAssignment] = []
    unassigned: list[UnassignedTarget] = []
    for target in sorted(targets, key=lambda item: (-item.risk_score, item.prp_location_id)):
        ranked = []
        for key, resource in available.items():
            distance = (
                geodesic_distance_meters(resource.start_location, target.location)
                if resource.start_location
                else None
            )
            ranked.append((distance is None, distance or 0.0, key, resource))
        if not ranked:
            unassigned.append(
                UnassignedTarget(
                    prp_location_id=target.prp_location_id,
                    reason="no_eligible_patrol_officer_pair",
                )
            )
            continue
        _, distance, key, resource = min(ranked)
        assignments.append(
            ProposedAssignment(
                patrol_unit_id=resource.patrol_unit_id,
                police_officer_id=resource.police_officer_id,
                prp_location_id=target.prp_location_id,
                straight_line_distance_meters=(
                    distance if resource.start_location is not None else None
                ),
            )
        )
        del available[key]
    return AssignmentPlan(assignments=tuple(assignments), unassigned=tuple(unassigned))

