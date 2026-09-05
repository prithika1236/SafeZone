"""Owner-scoped emergency contact operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import EmergencyContact, User
from app.schemas.emergency_contact import EmergencyContactCreate, EmergencyContactUpdate


async def list_contacts(session: AsyncSession, owner: User) -> list[EmergencyContact]:
    result = await session.scalars(
        select(EmergencyContact)
        .where(EmergencyContact.owner_id == owner.id, EmergencyContact.is_active.is_(True))
        .order_by(EmergencyContact.name, EmergencyContact.id)
    )
    return list(result.all())


async def get_contact(session: AsyncSession, owner: User, contact_id: UUID) -> EmergencyContact | None:
    return await session.scalar(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id,
            EmergencyContact.owner_id == owner.id,
            EmergencyContact.is_active.is_(True),
        )
    )


async def create_contact(
    session: AsyncSession, owner: User, data: EmergencyContactCreate
) -> EmergencyContact:
    contact = EmergencyContact(owner_id=owner.id, **data.model_dump())
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact


async def update_contact(
    session: AsyncSession, contact: EmergencyContact, data: EmergencyContactUpdate
) -> EmergencyContact:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    await session.commit()
    await session.refresh(contact)
    return contact


async def deactivate_contact(session: AsyncSession, contact: EmergencyContact) -> None:
    contact.is_active = False
    await session.commit()
