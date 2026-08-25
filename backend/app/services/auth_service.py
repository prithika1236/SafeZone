"""Authentication workflows independent from HTTP routing."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, DuplicateEmailError, InactiveAccountError
from app.core.security import (
    hash_password,
    perform_dummy_password_check,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import CitizenRegistration


def normalize_email(email: str) -> str:
    """Return the canonical form used for lookup and uniqueness."""
    return email.strip().casefold()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Retrieve a user by case-insensitive normalized email."""
    normalized_email = normalize_email(email)
    return await session.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )


async def register_citizen(
    session: AsyncSession,
    registration: CitizenRegistration,
) -> User:
    """Create an active citizen; privileged roles are never accepted publicly."""
    email = normalize_email(str(registration.email))
    if await get_user_by_email(session, email) is not None:
        raise DuplicateEmailError

    user = User(
        name=registration.name,
        email=email,
        password_hash=hash_password(registration.password.get_secret_value()),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateEmailError from exc
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Validate credentials without revealing whether an email exists."""
    user = await get_user_by_email(session, email)
    if user is None:
        perform_dummy_password_check(password)
        raise AuthenticationError

    valid, upgraded_hash = verify_password(password, user.password_hash)
    if not valid:
        raise AuthenticationError
    if not user.is_active:
        raise InactiveAccountError

    if upgraded_hash is not None:
        user.password_hash = upgraded_hash
        await session.commit()
    return user
