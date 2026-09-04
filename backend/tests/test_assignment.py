"""Deterministic patrol-allocation tests."""

import pytest

from app.optimization.assignment import AssignmentResource, AssignmentTarget, create_assignment_plan
from app.schemas.location import Coordinate


def resource(unit: str, officer: str, longitude: float, *, available: bool = True):
    return AssignmentResource(
        patrol_unit_id=unit,
        police_officer_id=officer,
        start_location=Coordinate(latitude=0, longitude=longitude),
        is_available=available,
    )


def target(identifier: str, longitude: float, risk: float):
    return AssignmentTarget(
        prp_location_id=identifier,
        location=Coordinate(latitude=0, longitude=longitude),
        risk_score=risk,
    )


def test_high_risk_prp_is_allocated_first_when_resources_are_limited() -> None:
    plan = create_assignment_plan(
        [resource("unit-1", "officer-1", 0)],
        [target("low", 0, 0.2), target("high", 0.01, 0.9)],
    )
    assert [item.prp_location_id for item in plan.assignments] == ["high"]
    assert [item.prp_location_id for item in plan.unassigned] == ["low"]


def test_nearest_available_pair_is_selected() -> None:
    plan = create_assignment_plan(
        [resource("far", "officer-2", 0.1), resource("near", "officer-1", 0.001)],
        [target("prp", 0, 1)],
    )
    assert plan.assignments[0].patrol_unit_id == "near"
    assert plan.assignments[0].straight_line_distance_meters is not None


def test_unavailable_resources_are_not_assigned() -> None:
    plan = create_assignment_plan(
        [resource("unit-1", "officer-1", 0, available=False)],
        [target("prp", 0, 1)],
    )
    assert plan.assignments == ()
    assert plan.unassigned[0].reason == "no_eligible_patrol_officer_pair"


def test_resource_is_used_only_once_for_simultaneous_plan() -> None:
    plan = create_assignment_plan(
        [resource("unit-1", "officer-1", 0)],
        [target("a", 0, 1), target("b", 0.01, 0.8)],
    )
    assert len(plan.assignments) == 1


def test_duplicate_resource_pairs_are_rejected() -> None:
    with pytest.raises(ValueError, match="resource pairs must be unique"):
        create_assignment_plan(
            [resource("unit-1", "officer-1", 0), resource("unit-1", "officer-1", 1)],
            [],
        )


def test_missing_location_is_explicit_not_zero_distance() -> None:
    unknown = AssignmentResource(
        patrol_unit_id="unknown",
        police_officer_id="officer-2",
        start_location=None,
    )
    plan = create_assignment_plan(
        [unknown, resource("located", "officer-1", 0.1)],
        [target("prp", 0, 1)],
    )
    assert plan.assignments[0].patrol_unit_id == "located"

