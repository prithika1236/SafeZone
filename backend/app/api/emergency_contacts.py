"""Private emergency-contact endpoints for authenticated Citizens."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_citizen
from app.database.dependencies import get_db_session
from app.models.user import EmergencyContact, User
from app.schemas.emergency_contact import (
    EmergencyContactCreate,
    EmergencyContactResponse,
    EmergencyContactUpdate,
)
from app.services import emergency_contact_service

router = APIRouter(prefix="/emergency-contacts", tags=["emergency contacts"])
Citizen = Annotated[User, Depends(require_citizen)]
Session = Annotated[AsyncSession, Depends(get_db_session)]


async def _owned_contact(session: AsyncSession, citizen: User, contact_id: UUID) -> EmergencyContact:
    contact = await emergency_contact_service.get_contact(session, citizen, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency contact not found")
    return contact


@router.get("", response_model=list[EmergencyContactResponse])
async def list_emergency_contacts(citizen: Citizen, session: Session) -> list[EmergencyContact]:
    return await emergency_contact_service.list_contacts(session, citizen)


@router.post("", response_model=EmergencyContactResponse, status_code=status.HTTP_201_CREATED)
async def create_emergency_contact(
    data: EmergencyContactCreate, citizen: Citizen, session: Session
) -> EmergencyContact:
    return await emergency_contact_service.create_contact(session, citizen, data)


@router.patch("/{contact_id}", response_model=EmergencyContactResponse)
async def update_emergency_contact(
    contact_id: UUID, data: EmergencyContactUpdate, citizen: Citizen, session: Session
) -> EmergencyContact:
    contact = await _owned_contact(session, citizen, contact_id)
    return await emergency_contact_service.update_contact(session, contact, data)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emergency_contact(
    contact_id: UUID, citizen: Citizen, session: Session
) -> Response:
    contact = await _owned_contact(session, citizen, contact_id)
    await emergency_contact_service.deactivate_contact(session, contact)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
