"""Citizen and Police emergency-dispatch endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_citizen, require_police
from app.core.config import Settings, get_settings
from app.database.dependencies import get_db_session
from app.models.enums import SOSStatus
from app.models.user import User
from app.schemas.sos import CitizenSOSResponse, PoliceSOSResponse, SOSCreate
from app.services.dispatch_service import (
    InvalidSOSTransitionError,
    SOSConflictError,
    SOSNotFoundError,
    cancel_citizen_sos,
    create_and_dispatch_sos,
    current_citizen_sos,
    current_police_sos,
    transition_police_sos,
)

router = APIRouter(prefix="/sos", tags=["SOS emergency dispatch"])
Citizen = Annotated[User, Depends(require_citizen)]
Police = Annotated[User, Depends(require_police)]
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, SOSNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("", response_model=CitizenSOSResponse, status_code=status.HTTP_201_CREATED)
async def create_sos(
    data: SOSCreate, session: Session, citizen: Citizen, settings: Configuration
) -> CitizenSOSResponse:
    try:
        return await create_and_dispatch_sos(session, citizen, data, settings)
    except SOSConflictError as exc:
        raise _error(exc) from exc


@router.get("/current", response_model=CitizenSOSResponse)
async def citizen_current_sos(session: Session, citizen: Citizen) -> CitizenSOSResponse:
    try:
        return await current_citizen_sos(session, citizen)
    except SOSNotFoundError as exc:
        raise _error(exc) from exc


@router.post("/{sos_id}/cancel", response_model=CitizenSOSResponse)
async def cancel_sos(
    sos_id: UUID, session: Session, citizen: Citizen, settings: Configuration
) -> CitizenSOSResponse:
    try:
        return await cancel_citizen_sos(session, citizen, sos_id, settings)
    except (SOSNotFoundError, InvalidSOSTransitionError) as exc:
        raise _error(exc) from exc


@router.get("/police/current", response_model=PoliceSOSResponse)
async def police_current_sos(session: Session, police: Police) -> PoliceSOSResponse:
    try:
        return await current_police_sos(session, police)
    except SOSNotFoundError as exc:
        raise _error(exc) from exc


async def _transition(
    sos_id: UUID, session: AsyncSession, police: User, target: SOSStatus,
    settings: Settings,
) -> PoliceSOSResponse:
    try:
        return await transition_police_sos(session, police, sos_id, target, settings)
    except (SOSNotFoundError, InvalidSOSTransitionError) as exc:
        raise _error(exc) from exc


@router.post("/{sos_id}/accept", response_model=PoliceSOSResponse)
async def accept_sos(sos_id: UUID, session: Session, police: Police, settings: Configuration) -> PoliceSOSResponse:
    return await _transition(sos_id, session, police, SOSStatus.ACCEPTED, settings)


@router.post("/{sos_id}/en-route", response_model=PoliceSOSResponse)
async def begin_response(sos_id: UUID, session: Session, police: Police, settings: Configuration) -> PoliceSOSResponse:
    return await _transition(sos_id, session, police, SOSStatus.EN_ROUTE, settings)


@router.post("/{sos_id}/arrive", response_model=PoliceSOSResponse)
async def arrive_at_emergency(sos_id: UUID, session: Session, police: Police, settings: Configuration) -> PoliceSOSResponse:
    return await _transition(sos_id, session, police, SOSStatus.ARRIVED, settings)


@router.post("/{sos_id}/resolve", response_model=PoliceSOSResponse)
async def resolve_sos(sos_id: UUID, session: Session, police: Police, settings: Configuration) -> PoliceSOSResponse:
    return await _transition(sos_id, session, police, SOSStatus.RESOLVED, settings)
