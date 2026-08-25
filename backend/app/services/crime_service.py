"""Crime persistence and ingestion operations kept outside HTTP routes."""

import csv
from io import StringIO
from datetime import datetime
from uuid import UUID

from geoalchemy2 import Geometry, WKTElement
from pydantic import ValidationError
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crime import CrimeIncident
from app.models.enums import CrimeIncidentStatus
from app.schemas.crime import (
    CrimeBulkRejection,
    CrimeBulkRequest,
    CrimeBulkResult,
    CrimeCreate,
    CrimePage,
    CrimeResponse,
    CrimeUpdate,
)


class CrimeNotFoundError(Exception):
    pass


class DuplicateCrimeError(Exception):
    pass


class CrimeCSVError(Exception):
    """Raised when an uploaded file is not a usable crime CSV."""


CSV_REQUIRED_FIELDS = frozenset(
    {
        "source_reference",
        "crime_type",
        "severity",
        "latitude",
        "longitude",
        "occurred_at",
        "reported_at",
    }
)
CSV_OPTIONAL_FIELDS = frozenset({"ward", "area", "status"})


def _point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def _response(row) -> CrimeResponse:
    incident, longitude, latitude = row
    return CrimeResponse(
        id=incident.id,
        crime_type=incident.crime_type,
        severity=incident.severity,
        latitude=latitude,
        longitude=longitude,
        occurred_at=incident.occurred_at,
        reported_at=incident.reported_at,
        ward=incident.ward,
        area=incident.area,
        source_reference=incident.source_reference,
        status=incident.status,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def _record_query():
    geometry = cast(CrimeIncident.location, Geometry(geometry_type="POINT", srid=4326))
    return select(CrimeIncident, func.ST_X(geometry), func.ST_Y(geometry))


async def create_crime(session: AsyncSession, data: CrimeCreate) -> CrimeResponse:
    if data.source_reference and await session.scalar(
        select(CrimeIncident.id).where(CrimeIncident.source_reference == data.source_reference)
    ):
        raise DuplicateCrimeError
    incident = CrimeIncident(
        **data.model_dump(exclude={"latitude", "longitude"}),
        location=_point(data.latitude, data.longitude),
    )
    session.add(incident)
    await session.commit()
    row = (await session.execute(_record_query().where(CrimeIncident.id == incident.id))).one()
    return _response(row)


async def get_crime(session: AsyncSession, incident_id: UUID) -> CrimeResponse:
    row = (await session.execute(_record_query().where(CrimeIncident.id == incident_id))).one_or_none()
    if row is None:
        raise CrimeNotFoundError
    return _response(row)


async def list_crimes(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    crime_type: str | None,
    status: CrimeIncidentStatus | None,
    severity: int | None,
    ward: str | None,
    area: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    min_latitude: float | None,
    min_longitude: float | None,
    max_latitude: float | None,
    max_longitude: float | None,
) -> CrimePage:
    filters = []
    if crime_type:
        filters.append(func.lower(CrimeIncident.crime_type) == crime_type.strip().lower())
    if status:
        filters.append(CrimeIncident.status == status)
    if severity is not None:
        filters.append(CrimeIncident.severity == severity)
    if ward:
        filters.append(func.lower(CrimeIncident.ward) == ward.strip().lower())
    if area:
        filters.append(func.lower(CrimeIncident.area) == area.strip().lower())
    if occurred_from:
        filters.append(CrimeIncident.occurred_at >= occurred_from)
    if occurred_to:
        filters.append(CrimeIncident.occurred_at <= occurred_to)
    if min_latitude is not None:
        geometry = cast(CrimeIncident.location, Geometry(geometry_type="POINT", srid=4326))
        envelope = func.ST_MakeEnvelope(
            min_longitude, min_latitude, max_longitude, max_latitude, 4326
        )
        filters.append(func.ST_Intersects(geometry, envelope))
    total = await session.scalar(select(func.count()).select_from(CrimeIncident).where(*filters))
    rows = (
        await session.execute(
            _record_query()
            .where(*filters)
            .order_by(CrimeIncident.occurred_at.desc(), CrimeIncident.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return CrimePage(items=[_response(row) for row in rows], total=total or 0, limit=limit, offset=offset)


async def update_crime(
    session: AsyncSession, incident_id: UUID, data: CrimeUpdate
) -> CrimeResponse:
    incident = await session.get(CrimeIncident, incident_id)
    if incident is None:
        raise CrimeNotFoundError
    values = data.model_dump(exclude_unset=True, exclude={"latitude", "longitude"})
    occurred_at = values.get("occurred_at", incident.occurred_at)
    reported_at = values.get("reported_at", incident.reported_at)
    if reported_at < occurred_at:
        raise ValueError("reported_at must not be earlier than occurred_at")
    for name, value in values.items():
        setattr(incident, name, value)
    if data.latitude is not None and data.longitude is not None:
        incident.location = _point(data.latitude, data.longitude)
    await session.commit()
    return await get_crime(session, incident_id)


async def deactivate_crime(session: AsyncSession, incident_id: UUID) -> CrimeResponse:
    return await update_crime(
        session, incident_id, CrimeUpdate(status=CrimeIncidentStatus.DISMISSED)
    )


async def bulk_ingest(session: AsyncSession, request: CrimeBulkRequest) -> CrimeBulkResult:
    parsed: list[tuple[int, CrimeCreate]] = []
    rejected: list[CrimeBulkRejection] = []
    for index, raw in enumerate(request.rows):
        try:
            item = CrimeCreate.model_validate(raw)
            if not item.source_reference:
                raise ValueError("source_reference is required for idempotent bulk ingestion")
            parsed.append((index, item))
        except (ValidationError, ValueError) as exc:
            rejected.append(CrimeBulkRejection(row=index, reason=str(exc)))

    references = [item.source_reference for _, item in parsed]
    existing = set(
        (await session.scalars(select(CrimeIncident.source_reference).where(
            CrimeIncident.source_reference.in_(references)
        ))).all()
    ) if references else set()
    seen: set[str] = set()
    duplicates: list[str] = []
    accepted = 0
    for _, item in parsed:
        reference = item.source_reference
        if reference in existing or reference in seen:
            duplicates.append(reference)
            continue
        seen.add(reference)
        session.add(CrimeIncident(
            **item.model_dump(exclude={"latitude", "longitude"}),
            location=_point(item.latitude, item.longitude),
        ))
        accepted += 1
    await session.commit()
    return CrimeBulkResult(
        total_rows=len(request.rows),
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
    )


def parse_crime_csv(content: bytes) -> CrimeBulkRequest:
    """Decode a CSV into raw rows so normal row validation remains authoritative."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CrimeCSVError("CSV must be UTF-8 encoded") from exc

    try:
        reader = csv.DictReader(StringIO(text, newline=""))
        headers = set(reader.fieldnames or [])
        missing = sorted(CSV_REQUIRED_FIELDS - headers)
        if missing:
            raise CrimeCSVError(f"Missing required CSV columns: {', '.join(missing)}")
        unsupported = sorted(headers - CSV_REQUIRED_FIELDS - CSV_OPTIONAL_FIELDS)
        if unsupported:
            raise CrimeCSVError(f"Unsupported CSV columns: {', '.join(unsupported)}")

        rows: list[dict[str, object]] = []
        for row in reader:
            if None in row:
                raise CrimeCSVError("A CSV row contains more values than the header")
            rows.append({key: (value if value != "" else None) for key, value in row.items()})
    except csv.Error as exc:
        raise CrimeCSVError(f"Malformed CSV: {exc}") from exc

    if not rows:
        raise CrimeCSVError("CSV contains no data rows")
    if len(rows) > 500:
        raise CrimeCSVError("CSV may contain at most 500 data rows")
    return CrimeBulkRequest(rows=rows)


async def ingest_crime_csv(session: AsyncSession, content: bytes) -> CrimeBulkResult:
    """Import independently validated CSV rows and return a complete summary."""
    return await bulk_ingest(session, parse_crime_csv(content))
