"""Password hashing and JWT access-token primitives."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.models.enums import UserRole
from app.models.user import User

password_hash = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = password_hash.hash("safezone-timing-defense-password")


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated identity claims extracted from an access token."""

    user_id: UUID
    role: UserRole


def hash_password(password: str) -> str:
    """Hash a password with the currently recommended Argon2 settings."""
    return password_hash.hash(password)


def verify_password(password: str, password_digest: str) -> tuple[bool, str | None]:
    """Verify a password and return an upgraded hash when parameters changed."""
    try:
        return password_hash.verify_and_update(password, password_digest)
    except UnknownHashError:
        return False, None


def perform_dummy_password_check(password: str) -> None:
    """Reduce email-enumeration timing differences for unknown accounts."""
    password_hash.verify(password, _DUMMY_PASSWORD_HASH)


def create_access_token(
    user: User,
    settings: Settings,
    *,
    issued_at: datetime | None = None,
) -> str:
    """Create a signed, short-lived JWT access token for one user."""
    now = issued_at or datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    """Validate a JWT and return only trusted claims used for authorization."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "role", "type", "iss", "aud", "iat", "nbf", "exp", "jti"]},
        )
        if payload["type"] != "access":
            raise AuthenticationError
        return AccessTokenClaims(
            user_id=UUID(payload["sub"]),
            role=UserRole(payload["role"]),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError from exc
