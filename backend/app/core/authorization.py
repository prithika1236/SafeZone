"""Reusable current-user and role-based authorization dependencies."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.database.dependencies import get_db_session
from app.models.enums import UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _authentication_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve a signed token to the current persisted user."""
    try:
        claims = decode_access_token(token, settings)
    except AuthenticationError as exc:
        raise _authentication_exception() from exc

    user = await session.scalar(select(User).where(User.id == claims.user_id))
    if user is None or user.role != claims.role:
        raise _authentication_exception()
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Reject authenticated identities disabled after token issuance."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return user


RoleDependency = Callable[..., Coroutine[Any, Any, User]]


def require_roles(*allowed_roles: UserRole) -> RoleDependency:
    """Build a reusable dependency allowing any role in `allowed_roles`."""
    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one allowed role is required")

    async def authorize(
        user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return authorize


require_citizen = require_roles(UserRole.CITIZEN)
require_police = require_roles(UserRole.POLICE)
require_admin = require_roles(UserRole.ADMIN)
require_admin_or_police = require_roles(UserRole.ADMIN, UserRole.POLICE)
