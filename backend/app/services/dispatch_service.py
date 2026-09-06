"""Transactional emergency dispatch, independent from strategic PRP optimization."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from geoalchemy2 import Geography, Geometry, WKTElement
from sqlalchemy import and_, cast, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.assignment import PatrolAssignment
from app.models.enums import AssignmentStatus, PatrolUnitStatus, SOSStatus
from app.models.location import LocationUpdate
from app.models.notification import DeviceRegistration
from app.models.police import PatrolUnit, PoliceOfficer
from app.models.sos import SOSRequest
from app.models.user import User
from app.schemas.location import Coordinate, RouteEstimate
from app.schemas.sos import CitizenSOSResponse, PoliceSOSResponse, SOSCreate
from app.services.location_service import (
    OSRMRoutingClient,
    RoutingClient,
    RoutingError,
)
from app.services.notification_service import NotificationMessage, build_push_adapter, safely_send_push
from app.services.realtime_service import sos_connections

logger = logging.getLogger(__name__)

OPEN_ASSIGNMENTS = (
    AssignmentStatus.ACTIVE,
    AssignmentStatus.ASSIGNED,
    AssignmentStatus.ACKNOWLEDGED,
    AssignmentStatus.AT_PRP,
)
ACTIVE_SOS_STATUSES = (
    SOSStatus.PENDING,
    SOSStatus.ASSIGNED,
    SOSStatus.ACCEPTED,
    SOSStatus.EN_ROUTE,
    SOSStatus.ARRIVED,
)


class SOSNotFoundError(Exception):
    pass


class SOSConflictError(Exception):
    pass


class InvalidSOSTransitionError(Exception):
    pass


@dataclass(frozen=True)
class DispatchCandidate:
    patrol_unit: PatrolUnit
    officer: PoliceOfficer
    location: Coordinate
    straight_line_distance_meters: float


def allowed_transition(current: SOSStatus, target: SOSStatus, *, citizen: bool = False) -> bool:
    if citizen:
        return target == SOSStatus.CANCELLED and current in (
            SOSStatus.PENDING,
            SOSStatus.ASSIGNED,
        )
    return target in {
        SOSStatus.ASSIGNED: {SOSStatus.ACCEPTED},
        SOSStatus.ACCEPTED: {SOSStatus.EN_ROUTE},
        SOSStatus.EN_ROUTE: {SOSStatus.ARRIVED},
        SOSStatus.ARRIVED: {SOSStatus.RESOLVED},
    }.get(current, set())


def choose_candidate(
    candidates: list[DispatchCandidate], routes: dict[UUID, RouteEstimate] | None
) -> tuple[DispatchCandidate | None, RouteEstimate | None, str | None]:
    if not candidates:
        return None, None, None
    if routes is not None and len(routes) == len(candidates):
        selected = min(
            candidates,
            key=lambda item: (routes[item.patrol_unit.id].distance_meters, str(item.patrol_unit.id)),
        )
        return selected, routes[selected.patrol_unit.id], "road_route"
    selected = min(
        candidates,
        key=lambda item: (item.straight_line_distance_meters, str(item.patrol_unit.id)),
    )
    return selected, None, "straight_line"


def _latest_locations():
    ranked = select(
        LocationUpdate.patrol_unit_id,
        LocationUpdate.location,
        LocationUpdate.recorded_at,
        func.row_number().over(
            partition_by=LocationUpdate.patrol_unit_id,
            order_by=(LocationUpdate.recorded_at.desc(), LocationUpdate.id.desc()),
        ).label("rank"),
    ).subquery("ranked_dispatch_locations")
    return select(
        ranked.c.patrol_unit_id, ranked.c.location, ranked.c.recorded_at
    ).where(ranked.c.rank == 1).subquery("latest_dispatch_locations")


async def _eligible_candidates(
    session: AsyncSession,
    location: Coordinate,
    settings: Settings,
) -> list[DispatchCandidate]:
    latest = _latest_locations()
    origin = cast(
        func.ST_SetSRID(func.ST_MakePoint(location.longitude, location.latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )
    distance = func.ST_Distance(latest.c.location, origin)
    longitude = func.ST_X(cast(latest.c.location, Geometry("POINT", 4326)))
    latitude = func.ST_Y(cast(latest.c.location, Geometry("POINT", 4326)))
    has_open_sos = exists(
        select(SOSRequest.id).where(
            SOSRequest.assigned_patrol_unit_id == PatrolUnit.id,
            SOSRequest.status.in_(ACTIVE_SOS_STATUSES),
        )
    )
    statement = (
        select(
            PatrolUnit,
            PoliceOfficer,
            latitude.label("latitude"),
            longitude.label("longitude"),
            distance.label("distance_meters"),
        )
        .join(latest, latest.c.patrol_unit_id == PatrolUnit.id)
        .join(PatrolAssignment, PatrolAssignment.patrol_unit_id == PatrolUnit.id)
        .join(PoliceOfficer, PoliceOfficer.id == PatrolAssignment.police_officer_id)
        .where(
            PatrolUnit.status.in_((PatrolUnitStatus.AVAILABLE, PatrolUnitStatus.ASSIGNED)),
            PatrolAssignment.status.in_(OPEN_ASSIGNMENTS),
            PatrolAssignment.shift_start <= func.now(),
            PatrolAssignment.shift_end > func.now(),
            func.ST_DWithin(latest.c.location, origin, settings.sos_dispatch_radius_meters),
            ~has_open_sos,
        )
        .order_by(distance, PatrolUnit.id)
        .limit(settings.sos_dispatch_candidate_limit)
        .with_for_update(of=PatrolUnit, skip_locked=True)
    )
    rows = (await session.execute(statement)).all()
    return [
        DispatchCandidate(
            patrol_unit=row[0], officer=row[1],
            location=Coordinate(latitude=row.latitude, longitude=row.longitude),
            straight_line_distance_meters=float(row.distance_meters),
        )
        for row in rows
    ]


async def _route_candidates(
    origin: Coordinate,
    candidates: list[DispatchCandidate],
    routing: RoutingClient,
) -> dict[UUID, RouteEstimate] | None:
    if not candidates:
        return None
    results = await asyncio.gather(
        *(routing.estimate_route(item.location, origin) for item in candidates),
        return_exceptions=True,
    )
    if any(isinstance(result, (Exception, RoutingError)) for result in results):
        return None
    return {
        candidate.patrol_unit.id: result
        for candidate, result in zip(candidates, results, strict=True)
        if isinstance(result, RouteEstimate)
    }


async def create_and_dispatch_sos(
    session: AsyncSession,
    citizen: User,
    data: SOSCreate,
    settings: Settings,
    *,
    routing_client: RoutingClient | None = None,
) -> CitizenSOSResponse:
    existing = await session.scalar(
        select(SOSRequest.id).where(
            SOSRequest.citizen_id == citizen.id,
            SOSRequest.status.in_(ACTIVE_SOS_STATUSES),
        ).with_for_update()
    )
    if existing is not None:
        raise SOSConflictError("Citizen already has an active SOS request")

    coordinate = Coordinate(latitude=data.latitude, longitude=data.longitude)
    sos = SOSRequest(
        citizen_id=citizen.id,
        location=WKTElement(f"POINT({coordinate.longitude} {coordinate.latitude})", srid=4326),
        status=SOSStatus.PENDING,
    )
    session.add(sos)
    await session.flush()

    candidates = await _eligible_candidates(session, coordinate, settings)
    routes = await _route_candidates(
        coordinate,
        candidates,
        routing_client or OSRMRoutingClient(
            settings.routing_service_base_url,
            timeout_seconds=settings.routing_service_timeout_seconds,
        ),
    )
    selected, route, source = choose_candidate(candidates, routes)
    if selected is not None:
        sos.assigned_patrol_unit_id = selected.patrol_unit.id
        sos.status = SOSStatus.ASSIGNED
        sos.distance_source = source
        sos.responder_distance_meters = (
            route.distance_meters if route else selected.straight_line_distance_meters
        )
        sos.estimated_duration_seconds = route.duration_seconds if route else None
        selected.patrol_unit.status = PatrolUnitStatus.RESPONDING
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise SOSConflictError("An active emergency already owns this citizen or patrol") from exc
    await session.refresh(sos)
    await _notify_sos_update(
        session, settings, citizen.id, sos, "sos_created",
        "Emergency request created", "Your SOS request has been received.",
    )
    if selected is not None:
        await _notify_sos_update(
            session, settings, selected.officer.user_id, sos, "sos_assigned",
            "New SOS assignment", "A new emergency response has been assigned.",
        )
        await _notify_sos_update(
            session, settings, citizen.id, sos, "patrol_assigned",
            "Patrol assigned", "A responder has been assigned to your emergency.",
        )
    return citizen_response(sos)


def citizen_response(sos: SOSRequest) -> CitizenSOSResponse:
    distance = float(sos.responder_distance_meters) if sos.responder_distance_meters else None
    approximate = int(round(distance / 100.0) * 100) if distance is not None else None
    return CitizenSOSResponse(
        id=sos.id, status=sos.status, created_at=sos.created_at, updated_at=sos.updated_at,
        patrol_assigned=sos.assigned_patrol_unit_id is not None,
        approximate_responder_distance_meters=approximate,
        estimated_duration_seconds=(
            int(round(float(sos.estimated_duration_seconds)))
            if sos.estimated_duration_seconds is not None else None
        ),
        accepted_at=sos.accepted_at, en_route_at=sos.en_route_at,
        arrived_at=sos.arrived_at, resolved_at=sos.resolved_at,
        cancelled_at=sos.cancelled_at,
    )


async def current_citizen_sos(session: AsyncSession, citizen: User) -> CitizenSOSResponse:
    sos = await session.scalar(
        select(SOSRequest).where(
            SOSRequest.citizen_id == citizen.id,
        ).order_by(SOSRequest.created_at.desc()).limit(1)
    )
    if sos is None:
        raise SOSNotFoundError("No SOS request found")
    return citizen_response(sos)


async def cancel_citizen_sos(
    session: AsyncSession, citizen: User, sos_id: UUID, settings: Settings
) -> CitizenSOSResponse:
    sos = await session.scalar(
        select(SOSRequest).where(
            SOSRequest.id == sos_id, SOSRequest.citizen_id == citizen.id
        ).with_for_update()
    )
    if sos is None:
        raise SOSNotFoundError("SOS request not found")
    if not allowed_transition(sos.status, SOSStatus.CANCELLED, citizen=True):
        raise InvalidSOSTransitionError(
            "SOS can only be cancelled before the officer accepts it"
        )
    sos.status = SOSStatus.CANCELLED
    sos.cancelled_at = datetime.now(UTC)
    await _release_patrol(session, sos)
    await session.commit()
    await session.refresh(sos)
    if sos.assigned_patrol_unit_id is not None:
        officer_user_id = await _officer_user_id(session, sos.assigned_patrol_unit_id)
        if officer_user_id:
            await _notify_sos_update(
                session, settings, officer_user_id, sos, "sos_cancelled",
                "SOS cancelled", "The assigned emergency was cancelled before acceptance.",
            )
    return citizen_response(sos)


def _police_sos_query(user_id: UUID):
    geometry = cast(SOSRequest.location, Geometry("POINT", 4326))
    return (
        select(SOSRequest, func.ST_X(geometry), func.ST_Y(geometry))
        .join(PatrolAssignment, PatrolAssignment.patrol_unit_id == SOSRequest.assigned_patrol_unit_id)
        .join(PoliceOfficer, PoliceOfficer.id == PatrolAssignment.police_officer_id)
        .where(
            PoliceOfficer.user_id == user_id,
            PatrolAssignment.status.in_(OPEN_ASSIGNMENTS),
            PatrolAssignment.shift_start <= func.now(),
            PatrolAssignment.shift_end > func.now(),
        )
    )


def _police_response(row) -> PoliceSOSResponse:
    sos, longitude, latitude = row
    return PoliceSOSResponse(
        id=sos.id, status=sos.status,
        emergency_location=Coordinate(latitude=latitude, longitude=longitude),
        created_at=sos.created_at, updated_at=sos.updated_at,
        responder_distance_meters=(float(sos.responder_distance_meters) if sos.responder_distance_meters else None),
        estimated_duration_seconds=(float(sos.estimated_duration_seconds) if sos.estimated_duration_seconds else None),
        distance_source=sos.distance_source, accepted_at=sos.accepted_at,
        en_route_at=sos.en_route_at, arrived_at=sos.arrived_at, resolved_at=sos.resolved_at,
    )


async def current_police_sos(session: AsyncSession, police: User) -> PoliceSOSResponse:
    row = (await session.execute(
        _police_sos_query(police.id)
        .where(SOSRequest.status.in_(ACTIVE_SOS_STATUSES[1:]))
        .order_by(SOSRequest.created_at).limit(1)
    )).one_or_none()
    if row is None:
        raise SOSNotFoundError("No active SOS dispatch")
    return _police_response(row)


async def transition_police_sos(
    session: AsyncSession, police: User, sos_id: UUID, target: SOSStatus,
    settings: Settings,
) -> PoliceSOSResponse:
    row = (await session.execute(
        _police_sos_query(police.id).where(SOSRequest.id == sos_id).with_for_update(of=SOSRequest)
    )).one_or_none()
    if row is None:
        raise SOSNotFoundError("SOS dispatch not found")
    sos = row[0]
    if not allowed_transition(sos.status, target):
        raise InvalidSOSTransitionError(f"Cannot change SOS from {sos.status} to {target}")
    now = datetime.now(UTC)
    sos.status = target
    timestamp_field = {
        SOSStatus.ACCEPTED: "accepted_at", SOSStatus.EN_ROUTE: "en_route_at",
        SOSStatus.ARRIVED: "arrived_at", SOSStatus.RESOLVED: "resolved_at",
    }[target]
    setattr(sos, timestamp_field, now)
    if target == SOSStatus.RESOLVED:
        await _release_patrol(session, sos)
    await session.commit()
    updated = (await session.execute(_police_sos_query(police.id).where(SOSRequest.id == sos_id))).one()
    await _notify_sos_update(
        session, settings, sos.citizen_id, sos, "sos_status_changed",
        "Emergency status updated", f"Responder status: {target.value.replace('_', ' ').title()}.",
    )
    return _police_response(updated)


async def _release_patrol(session: AsyncSession, sos: SOSRequest) -> None:
    if sos.assigned_patrol_unit_id is None:
        return
    unit = await session.get(PatrolUnit, sos.assigned_patrol_unit_id)
    if unit is None:
        return
    active_assignment = await session.scalar(
        select(PatrolAssignment.id).where(
            PatrolAssignment.patrol_unit_id == unit.id,
            PatrolAssignment.status.in_(OPEN_ASSIGNMENTS),
            PatrolAssignment.shift_start <= func.now(),
            PatrolAssignment.shift_end > func.now(),
        ).limit(1)
    )
    unit.status = PatrolUnitStatus.ASSIGNED if active_assignment else PatrolUnitStatus.AVAILABLE


async def _officer_user_id(session: AsyncSession, patrol_unit_id: UUID) -> UUID | None:
    return await session.scalar(
        select(PoliceOfficer.user_id)
        .join(PatrolAssignment, PatrolAssignment.police_officer_id == PoliceOfficer.id)
        .where(
            PatrolAssignment.patrol_unit_id == patrol_unit_id,
            PatrolAssignment.status.in_(OPEN_ASSIGNMENTS),
        ).limit(1)
    )


async def _notify_sos_update(
    session: AsyncSession, settings: Settings, user_id: UUID, sos: SOSRequest,
    event: str, title: str, body: str,
) -> None:
    """Best-effort delivery must never roll back or falsify emergency state."""
    payload = {"event": event, "sos_id": str(sos.id), "status": sos.status.value}
    await sos_connections.publish(user_id, payload)
    try:
        tokens = list((await session.scalars(
            select(DeviceRegistration.token).where(
                DeviceRegistration.user_id == user_id,
                DeviceRegistration.is_active.is_(True),
            )
        )).all())
        adapter = build_push_adapter(settings)
        await safely_send_push(adapter, tokens, NotificationMessage(title, body, payload))
    except Exception:
        logger.exception("notification_preparation_failed", extra={"event": event})
