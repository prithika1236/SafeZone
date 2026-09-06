"""Controlled police location and device-registration operations."""

from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.assignment import PatrolAssignment
from app.models.enums import AssignmentStatus, SOSStatus
from app.models.location import LocationUpdate
from app.models.notification import DeviceRegistration
from app.models.police import PoliceOfficer
from app.models.sos import SOSRequest
from app.models.user import User
from app.schemas.live import DeviceRegistrationCreate, PoliceLocationCreate


class LiveLocationError(Exception): pass
class LocationRateLimitError(LiveLocationError): pass

ACTIVE_ASSIGNMENTS = (
    AssignmentStatus.ASSIGNED, AssignmentStatus.ACKNOWLEDGED,
    AssignmentStatus.AT_PRP, AssignmentStatus.ACTIVE,
)
ACTIVE_RESPONSES = (SOSStatus.ASSIGNED, SOSStatus.ACCEPTED, SOSStatus.EN_ROUTE, SOSStatus.ARRIVED)


def is_update_interval_allowed(
    latest_at: datetime | None, now: datetime, minimum_seconds: int
) -> bool:
    return latest_at is None or latest_at <= now - timedelta(seconds=minimum_seconds)


async def record_police_location(
    session: AsyncSession, police: User, data: PoliceLocationCreate, settings: Settings
) -> LocationUpdate:
    if data.accuracy_meters is not None and data.accuracy_meters > settings.police_location_maximum_accuracy_meters:
        raise LiveLocationError("Location accuracy is insufficient for operational use")
    row = (await session.execute(
        select(PatrolAssignment, PoliceOfficer)
        .join(PoliceOfficer, PoliceOfficer.id == PatrolAssignment.police_officer_id)
        .where(
            PoliceOfficer.user_id == police.id,
            PatrolAssignment.status.in_(ACTIVE_ASSIGNMENTS),
            PatrolAssignment.shift_start <= datetime.now(UTC),
            PatrolAssignment.shift_end > datetime.now(UTC),
        ).order_by(PatrolAssignment.shift_start.desc()).limit(1)
    )).one_or_none()
    if row is None:
        raise LiveLocationError("Police location is accepted only during an active shift")
    assignment = row[0]
    latest = await session.scalar(
        select(LocationUpdate).where(LocationUpdate.patrol_unit_id == assignment.patrol_unit_id)
        .order_by(LocationUpdate.recorded_at.desc()).limit(1)
    )
    now = datetime.now(UTC)
    if latest and not is_update_interval_allowed(
        latest.recorded_at, now, settings.police_location_minimum_interval_seconds
    ):
        raise LocationRateLimitError("Location update interval is too short")
    sos_id = await session.scalar(
        select(SOSRequest.id).where(
            SOSRequest.assigned_patrol_unit_id == assignment.patrol_unit_id,
            SOSRequest.status.in_(ACTIVE_RESPONSES),
        ).limit(1)
    )
    update = LocationUpdate(
        patrol_unit_id=assignment.patrol_unit_id, sos_request_id=sos_id,
        location=WKTElement(f"POINT({data.longitude} {data.latitude})", srid=4326),
        accuracy_meters=data.accuracy_meters, recorded_at=now,
    )
    session.add(update)
    await session.commit()
    await session.refresh(update)
    return update


async def register_device(session: AsyncSession, user: User, data: DeviceRegistrationCreate) -> None:
    existing = await session.scalar(select(DeviceRegistration).where(DeviceRegistration.token == data.token))
    if existing:
        existing.user_id, existing.platform, existing.is_active = user.id, data.platform, True
    else:
        session.add(DeviceRegistration(user_id=user.id, token=data.token, platform=data.platform))
    await session.commit()
