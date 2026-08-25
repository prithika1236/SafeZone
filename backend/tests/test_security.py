from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User


def make_test_settings() -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://safezone:test@localhost:5432/safezone_test",
        JWT_SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        JWT_ISSUER="safezone-test",
        JWT_AUDIENCE="safezone-test-clients",
    )


def make_user(role: UserRole = UserRole.CITIZEN) -> User:
    return User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        password_hash=hash_password("Correct-Password-123"),
        role=role,
        is_active=True,
    )


def test_argon2_password_hashing_and_verification() -> None:
    password = "Correct-Password-123"
    password_digest = hash_password(password)

    valid, replacement = verify_password(password, password_digest)
    invalid, _ = verify_password("incorrect-password", password_digest)

    assert password_digest.startswith("$argon2")
    assert valid is True
    assert replacement is None
    assert invalid is False


def test_access_token_round_trip() -> None:
    user = make_user(UserRole.POLICE)
    settings = make_test_settings()

    token = create_access_token(user, settings)
    claims = decode_access_token(token, settings)

    assert claims.user_id == user.id
    assert claims.role is UserRole.POLICE


def test_expired_access_token_is_rejected() -> None:
    user = make_user()
    settings = make_test_settings()
    token = create_access_token(
        user,
        settings,
        issued_at=datetime.now(UTC) - timedelta(hours=1),
    )

    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)
