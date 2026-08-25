"""Authentication and current-profile HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_active_user
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, DuplicateEmailError, InactiveAccountError
from app.core.security import create_access_token
from app.database.dependencies import get_db_session
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, CitizenRegistration, UserProfile
from app.services.auth_service import authenticate_user, register_citizen

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register/citizen",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
)
async def register_citizen_endpoint(
    registration: CitizenRegistration,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Register a citizen without exposing privileged role selection."""
    try:
        return await register_citizen(session, registration)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    """Authenticate an email/password pair and issue one access token."""
    try:
        user = await authenticate_user(session, form.username, form.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from exc

    return AccessTokenResponse(
        access_token=create_access_token(user, settings),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserProfile)
async def current_profile(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Return the active authenticated user's safe profile."""
    return user
