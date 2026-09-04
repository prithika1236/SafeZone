"""Persistence and lifecycle orchestration for strategic patrol assignments."""

from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import PatrolAssignment
from app.models.enums import (
    AssignmentStatus,
    OfficerAvailability,
    OptimizationRunStatus,
    PRPStatus,
    PatrolUnitStatus,
)
from app.models.location import LocationUpdate
from app.models.optimization import OptimizationRun, PRPLocation
from app.models.police import PatrolUnit, PoliceOfficer
from app.optimization.assignment import AssignmentResource, AssignmentTarget, create_assignment_plan
from app.schemas.assignment import (
    AssignmentBatchResponse,
    AssignmentList,
    AssignmentResponse,
    ManualAssignmentOverride,
)
from app.schemas.location import Coordinate

OPEN_ASSIGNMENT_STATUSES = (
    AssignmentStatus.PLANNED,
    AssignmentStatus.ACTIVE,
    AssignmentStatus.ASSIGNED,
    AssignmentStatus.ACKNOWLEDGED,
    AssignmentStatus.AT_PRP,
)


class AssignmentNotFoundError(Exception):
    pass


class AssignmentConflictError(Exception):
    pass


class InvalidAssignmentStateError(Exception):
    pass


def _latest_locations():
    ranked = select(
        LocationUpdate.patrol_unit_id,
        LocationUpdate.location,
        func.row_number()
        .over(
            partition_by=LocationUpdate.patrol_unit_id,
            order_by=(LocationUpdate.recorded_at.desc(), LocationUpdate.id.desc()),
        )
        .label("rank"),
    ).subquery()
    return select(ranked.c.patrol_unit_id, ranked.c.location).where(ranked.c.rank == 1).subquery()


def _assignment_query():
    geometry = cast(PRPLocation.location, Geometry(geometry_type="POINT", srid=4326))
    return (
        select(PatrolAssignment, func.ST_X(geometry), func.ST_Y(geometry))
        .join(PRPLocation, PRPLocation.id == PatrolAssignment.prp_location_id)
    )


def _response(row, distance: float | None = None) -> AssignmentResponse:
    assignment, longitude, latitude = row
    return AssignmentResponse(
        id=assignment.id,
        patrol_unit_id=assignment.patrol_unit_id,
        police_officer_id=assignment.police_officer_id,
        prp_location_id=assignment.prp_location_id,
        prp_location=Coordinate(latitude=latitude, longitude=longitude),
        shift_start=assignment.shift_start,
        shift_end=assignment.shift_end,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        updated_at=assignment.updated_at,
        straight_line_distance_meters=distance,
    )


async def _get_response(session: AsyncSession, assignment_id: UUID) -> AssignmentResponse:
    row = (await session.execute(_assignment_query().where(PatrolAssignment.id == assignment_id))).one_or_none()
    if row is None:
        raise AssignmentNotFoundError
    return _response(row)


def _overlaps(start, end):
    return and_(PatrolAssignment.shift_start < end, PatrolAssignment.shift_end > start)


async def _has_conflict(
    session: AsyncSession,
    *,
    unit_id: UUID,
    officer_id: UUID,
    shift_start,
    shift_end,
    exclude_assignment_id: UUID | None = None,
) -> bool:
    statement = select(PatrolAssignment.id).where(
        PatrolAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
        _overlaps(shift_start, shift_end),
        or_(
            PatrolAssignment.patrol_unit_id == unit_id,
            PatrolAssignment.police_officer_id == officer_id,
        ),
    )
    if exclude_assignment_id:
        statement = statement.where(PatrolAssignment.id != exclude_assignment_id)
    return await session.scalar(statement.limit(1)) is not None


async def create_automatic_assignments(
    session: AsyncSession, optimization_run_id: UUID
) -> AssignmentBatchResponse:
    run = await session.scalar(
        select(OptimizationRun).where(OptimizationRun.id == optimization_run_id)
    )
    if run is None:
        raise AssignmentNotFoundError("Optimization run not found")
    if run.status != OptimizationRunStatus.COMPLETED:
        raise InvalidAssignmentStateError("Optimization run must be completed")

    geometry = cast(PRPLocation.location, Geometry(geometry_type="POINT", srid=4326))
    prp_rows = (
        await session.execute(
            select(PRPLocation, func.ST_X(geometry), func.ST_Y(geometry))
            .where(
                PRPLocation.optimization_run_id == optimization_run_id,
                PRPLocation.status.in_((PRPStatus.APPROVED, PRPStatus.ACTIVE)),
            )
            .order_by(PRPLocation.id)
        )
    ).all()
    if not prp_rows:
        raise InvalidAssignmentStateError("Run has no approved PRPs")
    shift_start = min(row[0].shift_start for row in prp_rows)
    shift_end = max(row[0].shift_end for row in prp_rows)

    existing_prp_ids = set(
        await session.scalars(
            select(PatrolAssignment.prp_location_id).where(
                PatrolAssignment.prp_location_id.in_([row[0].id for row in prp_rows]),
                PatrolAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
                _overlaps(shift_start, shift_end),
            )
        )
    )
    targets = [
        AssignmentTarget(
            prp_location_id=str(prp.id),
            location=Coordinate(latitude=latitude, longitude=longitude),
            risk_score=float(prp.risk_score),
        )
        for prp, longitude, latitude in prp_rows
        if prp.id not in existing_prp_ids
    ]

    latest = _latest_locations()
    latest_geometry = cast(latest.c.location, Geometry("POINT", 4326))
    unit_rows = (
        await session.execute(
            select(
                PatrolUnit,
                func.ST_X(latest_geometry).label("longitude"),
                func.ST_Y(latest_geometry).label("latitude"),
            )
            .outerjoin(latest, latest.c.patrol_unit_id == PatrolUnit.id)
            .where(PatrolUnit.status == PatrolUnitStatus.AVAILABLE)
            .order_by(PatrolUnit.unit_identifier, PatrolUnit.id)
        )
    ).all()
    officers = list(
        await session.scalars(
            select(PoliceOfficer)
            .where(PoliceOfficer.availability_status == OfficerAvailability.AVAILABLE)
            .order_by(PoliceOfficer.badge_identifier, PoliceOfficer.id)
        )
    )
    geometry_rows = [
        (
            row[0],
            Coordinate(latitude=row.latitude, longitude=row.longitude)
            if row.latitude is not None and row.longitude is not None
            else None,
        )
        for row in unit_rows
    ]

    resources: list[AssignmentResource] = []
    paired_models: dict[tuple[str, str], tuple[PatrolUnit, PoliceOfficer]] = {}
    for (unit, coordinate), officer in zip(geometry_rows, officers, strict=False):
        conflict = await _has_conflict(
            session,
            unit_id=unit.id,
            officer_id=officer.id,
            shift_start=shift_start,
            shift_end=shift_end,
        )
        key = (str(unit.id), str(officer.id))
        paired_models[key] = (unit, officer)
        resources.append(
            AssignmentResource(
                patrol_unit_id=key[0],
                police_officer_id=key[1],
                start_location=coordinate,
                is_available=not conflict,
            )
        )

    plan = create_assignment_plan(resources, targets)
    distances: dict[UUID, float | None] = {}
    created: list[PatrolAssignment] = []
    prps = {str(row[0].id): row[0] for row in prp_rows}
    for proposed in plan.assignments:
        unit, officer = paired_models[(proposed.patrol_unit_id, proposed.police_officer_id)]
        prp = prps[proposed.prp_location_id]
        assignment = PatrolAssignment(
            patrol_unit_id=unit.id,
            police_officer_id=officer.id,
            prp_location_id=prp.id,
            shift_start=prp.shift_start,
            shift_end=prp.shift_end,
            status=AssignmentStatus.ASSIGNED,
        )
        session.add(assignment)
        unit.status = PatrolUnitStatus.ASSIGNED
        officer.availability_status = OfficerAvailability.ASSIGNED
        created.append(assignment)
        distances[id(assignment)] = proposed.straight_line_distance_meters
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AssignmentConflictError("A patrol or officer acquired an overlapping assignment") from exc

    responses = []
    for assignment in created:
        item = await _get_response(session, assignment.id)
        responses.append(
            item.model_copy(update={"straight_line_distance_meters": distances[id(assignment)]})
        )
    unassigned = tuple(UUID(item.prp_location_id) for item in plan.unassigned)
    unassigned += tuple(sorted(existing_prp_ids, key=str))
    return AssignmentBatchResponse(assignments=tuple(responses), unassigned_prp_ids=unassigned)


async def list_assignments(
    session: AsyncSession, *, limit: int = 100, offset: int = 0
) -> AssignmentList:
    total = await session.scalar(select(func.count()).select_from(PatrolAssignment)) or 0
    rows = (
        await session.execute(
            _assignment_query()
            .order_by(PatrolAssignment.shift_start.desc(), PatrolAssignment.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return AssignmentList(items=tuple(_response(row) for row in rows), total=total)


async def get_assignment(session: AsyncSession, assignment_id: UUID) -> AssignmentResponse:
    return await _get_response(session, assignment_id)


async def current_police_assignment(
    session: AsyncSession, user_id: UUID
) -> AssignmentResponse:
    row = (
        await session.execute(
            _assignment_query()
            .join(PoliceOfficer, PoliceOfficer.id == PatrolAssignment.police_officer_id)
            .where(
                PoliceOfficer.user_id == user_id,
                PatrolAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
                PatrolAssignment.shift_end > func.now(),
            )
            .order_by(PatrolAssignment.shift_start, PatrolAssignment.id)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise AssignmentNotFoundError
    return _response(row)


async def _release_resources(session: AsyncSession, assignment: PatrolAssignment) -> None:
    other = await session.scalar(
        select(PatrolAssignment.id).where(
            PatrolAssignment.id != assignment.id,
            PatrolAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
            or_(
                PatrolAssignment.patrol_unit_id == assignment.patrol_unit_id,
                PatrolAssignment.police_officer_id == assignment.police_officer_id,
            ),
        ).limit(1)
    )
    if other is None:
        unit = await session.get(PatrolUnit, assignment.patrol_unit_id)
        officer = await session.get(PoliceOfficer, assignment.police_officer_id)
        if unit:
            unit.status = PatrolUnitStatus.AVAILABLE
        if officer:
            officer.availability_status = OfficerAvailability.AVAILABLE


async def transition_assignment(
    session: AsyncSession,
    assignment_id: UUID,
    *,
    user_id: UUID | None,
    target_status: AssignmentStatus,
) -> AssignmentResponse:
    assignment = await session.get(PatrolAssignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError
    if user_id is not None:
        officer = await session.get(PoliceOfficer, assignment.police_officer_id)
        if officer is None or officer.user_id != user_id:
            raise AssignmentNotFoundError
    allowed = {
        AssignmentStatus.ASSIGNED: {AssignmentStatus.ACKNOWLEDGED, AssignmentStatus.CANCELLED},
        AssignmentStatus.ACKNOWLEDGED: {AssignmentStatus.AT_PRP, AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED},
        AssignmentStatus.AT_PRP: {AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED},
    }
    if target_status not in allowed.get(assignment.status, set()):
        raise InvalidAssignmentStateError(
            f"Cannot change assignment from {assignment.status} to {target_status}"
        )
    assignment.status = target_status
    if target_status in (AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED):
        await _release_resources(session, assignment)
    await session.commit()
    return await _get_response(session, assignment_id)


async def override_assignment(
    session: AsyncSession, assignment_id: UUID, data: ManualAssignmentOverride
) -> AssignmentResponse:
    assignment = await session.get(PatrolAssignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError
    if assignment.status not in (AssignmentStatus.ASSIGNED, AssignmentStatus.ACKNOWLEDGED):
        raise InvalidAssignmentStateError("Only pending or acknowledged assignments can be overridden")
    unit = await session.get(PatrolUnit, data.patrol_unit_id)
    officer = await session.get(PoliceOfficer, data.police_officer_id)
    prp = await session.get(PRPLocation, data.prp_location_id or assignment.prp_location_id)
    if unit is None or officer is None or prp is None:
        raise AssignmentNotFoundError("Override resource not found")
    if prp.status not in (PRPStatus.APPROVED, PRPStatus.ACTIVE):
        raise InvalidAssignmentStateError("Override PRP must be approved or active")
    if unit.id != assignment.patrol_unit_id and unit.status != PatrolUnitStatus.AVAILABLE:
        raise InvalidAssignmentStateError("Replacement patrol unit is unavailable")
    if officer.id != assignment.police_officer_id and officer.availability_status != OfficerAvailability.AVAILABLE:
        raise InvalidAssignmentStateError("Replacement officer is unavailable")
    if await _has_conflict(
        session,
        unit_id=unit.id,
        officer_id=officer.id,
        shift_start=prp.shift_start,
        shift_end=prp.shift_end,
        exclude_assignment_id=assignment.id,
    ):
        raise AssignmentConflictError("Replacement patrol or officer has an overlapping assignment")
    old_unit_id, old_officer_id = assignment.patrol_unit_id, assignment.police_officer_id
    assignment.patrol_unit_id = unit.id
    assignment.police_officer_id = officer.id
    assignment.prp_location_id = prp.id
    assignment.shift_start = prp.shift_start
    assignment.shift_end = prp.shift_end
    assignment.status = AssignmentStatus.ASSIGNED
    unit.status = PatrolUnitStatus.ASSIGNED
    officer.availability_status = OfficerAvailability.ASSIGNED
    if old_unit_id != unit.id:
        old_unit = await session.get(PatrolUnit, old_unit_id)
        if old_unit:
            old_unit.status = PatrolUnitStatus.AVAILABLE
    if old_officer_id != officer.id:
        old_officer = await session.get(PoliceOfficer, old_officer_id)
        if old_officer:
            old_officer.availability_status = OfficerAvailability.AVAILABLE
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AssignmentConflictError("Override conflicts with an overlapping assignment") from exc
    return await _get_response(session, assignment_id)
