"""Authorized crime-incident management endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin, require_admin_or_police
from app.core.config import Settings, get_settings
from app.database.dependencies import get_db_session
from app.models.enums import CrimeIncidentStatus
from app.models.user import User
from app.schemas.crime import CrimeBulkRequest, CrimeBulkResult, CrimeCreate, CrimePage, CrimeResponse, CrimeUpdate
from app.services.crime_service import (
    CrimeCSVError,
    CrimeNotFoundError,
    DuplicateCrimeError,
    bulk_ingest,
    create_crime,
    deactivate_crime,
    get_crime,
    ingest_crime_csv,
    list_crimes,
    update_crime,
)

router = APIRouter(prefix="/crimes", tags=["crime management"])
Authorized = Annotated[User, Depends(require_admin_or_police)]
Admin = Annotated[User, Depends(require_admin)]
Session = Annotated[AsyncSession, Depends(get_db_session)]


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail="Crime incident not found")


@router.post("", response_model=CrimeResponse, status_code=status.HTTP_201_CREATED)
async def create(data: CrimeCreate, session: Session, _: Authorized) -> CrimeResponse:
    try:
        return await create_crime(session, data)
    except DuplicateCrimeError as exc:
        raise HTTPException(status_code=409, detail="Source reference already exists") from exc


@router.get("", response_model=CrimePage)
async def list_all(
    session: Session,
    _: Authorized,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    crime_type: str | None = None,
    incident_status: CrimeIncidentStatus | None = Query(default=None, alias="status"),
    severity: Annotated[int | None, Query(ge=1, le=5)] = None,
    ward: str | None = None,
    area: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    min_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> CrimePage:
    if occurred_from and occurred_to and occurred_to < occurred_from:
        raise HTTPException(status_code=422, detail="occurred_to must not precede occurred_from")
    if any(value is not None for value in (occurred_from, occurred_to)) and any(
        value is not None and value.tzinfo is None for value in (occurred_from, occurred_to)
    ):
        raise HTTPException(status_code=422, detail="Date filters must include timezone information")
    bounds = (min_latitude, min_longitude, max_latitude, max_longitude)
    if any(value is not None for value in bounds) and not all(value is not None for value in bounds):
        raise HTTPException(status_code=422, detail="All four bounding-box coordinates are required")
    if min_latitude is not None and (
        min_latitude >= max_latitude or min_longitude >= max_longitude
    ):
        raise HTTPException(status_code=422, detail="Bounding-box minimums must be below maximums")
    return await list_crimes(
        session,
        limit=limit,
        offset=offset,
        crime_type=crime_type,
        status=incident_status,
        severity=severity,
        ward=ward,
        area=area,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        min_latitude=min_latitude,
        min_longitude=min_longitude,
        max_latitude=max_latitude,
        max_longitude=max_longitude,
    )


@router.post("/bulk", response_model=CrimeBulkResult)
async def bulk(data: CrimeBulkRequest, session: Session, _: Authorized) -> CrimeBulkResult:
    return await bulk_ingest(session, data)


@router.post("/import/csv", response_model=CrimeBulkResult)
async def import_csv(
    session: Session,
    _: Admin,
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="UTF-8 crime incident CSV")],
) -> CrimeBulkResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="A .csv file is required")
    content = await file.read(settings.crime_csv_max_bytes + 1)
    if len(content) > settings.crime_csv_max_bytes:
        raise HTTPException(status_code=413, detail="CSV file exceeds the configured size limit")
    try:
        return await ingest_crime_csv(session, content)
    except CrimeCSVError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{incident_id}", response_model=CrimeResponse)
async def retrieve(incident_id: UUID, session: Session, _: Authorized) -> CrimeResponse:
    try:
        return await get_crime(session, incident_id)
    except CrimeNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/{incident_id}", response_model=CrimeResponse)
async def update(incident_id: UUID, data: CrimeUpdate, session: Session, _: Authorized) -> CrimeResponse:
    try:
        return await update_crime(session, incident_id, data)
    except CrimeNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{incident_id}", response_model=CrimeResponse)
async def deactivate(incident_id: UUID, session: Session, _: Admin) -> CrimeResponse:
    try:
        return await deactivate_crime(session, incident_id)
    except CrimeNotFoundError as exc:
        raise _not_found(exc) from exc
