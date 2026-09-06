"""Deterministic SOS selection and lifecycle tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.models.enums import PatrolUnitStatus, SOSStatus
from app.models.police import PatrolUnit, PoliceOfficer
from app.schemas.location import Coordinate, RouteEstimate
from app.services.dispatch_service import DispatchCandidate, allowed_transition, choose_candidate


def candidate(identifier: int, distance: float) -> DispatchCandidate:
    unit = PatrolUnit(
        id=UUID(int=identifier), unit_identifier=f"UNIT-{identifier}",
        status=PatrolUnitStatus.AVAILABLE, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    officer = PoliceOfficer(id=UUID(int=identifier + 100), user_id=UUID(int=identifier + 200), badge_identifier=f"B-{identifier}")
    return DispatchCandidate(
        patrol_unit=unit, officer=officer,
        location=Coordinate(latitude=9.35, longitude=78.51 + identifier / 1000),
        straight_line_distance_meters=distance,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (SOSStatus.ASSIGNED, SOSStatus.ACCEPTED),
        (SOSStatus.ACCEPTED, SOSStatus.EN_ROUTE),
        (SOSStatus.EN_ROUTE, SOSStatus.ARRIVED),
        (SOSStatus.ARRIVED, SOSStatus.RESOLVED),
    ],
)
def test_valid_police_status_transitions(current: SOSStatus, target: SOSStatus) -> None:
    assert allowed_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (SOSStatus.ASSIGNED, SOSStatus.ARRIVED),
        (SOSStatus.ACCEPTED, SOSStatus.RESOLVED),
        (SOSStatus.RESOLVED, SOSStatus.EN_ROUTE),
        (SOSStatus.CANCELLED, SOSStatus.ACCEPTED),
    ],
)
def test_invalid_police_status_transitions(current: SOSStatus, target: SOSStatus) -> None:
    assert not allowed_transition(current, target)


def test_citizen_can_cancel_only_before_acceptance() -> None:
    assert allowed_transition(SOSStatus.PENDING, SOSStatus.CANCELLED, citizen=True)
    assert allowed_transition(SOSStatus.ASSIGNED, SOSStatus.CANCELLED, citizen=True)
    assert not allowed_transition(SOSStatus.ACCEPTED, SOSStatus.CANCELLED, citizen=True)


def test_straight_line_fallback_is_deterministic() -> None:
    far, near = candidate(1, 900), candidate(2, 300)
    selected, route, source = choose_candidate([far, near], None)
    assert selected == near
    assert route is None
    assert source == "straight_line"


def test_complete_routes_choose_shortest_road_distance() -> None:
    first, second = candidate(1, 200), candidate(2, 300)
    routes = {
        first.patrol_unit.id: RouteEstimate(distance_meters=900, duration_seconds=200, provider="test"),
        second.patrol_unit.id: RouteEstimate(distance_meters=500, duration_seconds=120, provider="test"),
    }
    selected, route, source = choose_candidate([first, second], routes)
    assert selected == second
    assert route == routes[second.patrol_unit.id]
    assert source == "road_route"


def test_partial_route_results_use_consistent_spatial_fallback() -> None:
    near, far = candidate(1, 100), candidate(2, 500)
    partial = {far.patrol_unit.id: RouteEstimate(distance_meters=50, duration_seconds=10, provider="test")}
    selected, route, source = choose_candidate([near, far], partial)
    assert selected == near
    assert route is None
    assert source == "straight_line"


def test_no_candidates_is_handled() -> None:
    assert choose_candidate([], None) == (None, None, None)
