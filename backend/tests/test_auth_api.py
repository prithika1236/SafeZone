import asyncio
from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Depends
from httpx import ASGITransport, AsyncClient

from app.core.authorization import require_admin
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.database.dependencies import get_db_session
from app.main import create_app
from app.models.enums import UserRole
from app.models.user import User

TEST_SETTINGS = Settings(
    _env_file=None,
    APP_ENV="test",
    DATABASE_URL="postgresql+asyncpg://safezone:test@localhost:5432/safezone_test",
    JWT_SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
    JWT_ISSUER="safezone-test",
    JWT_AUDIENCE="safezone-test-clients",
)


class FakeSession:
    """Small isolated async-session substitute for auth transport tests."""

    def __init__(self, *scalar_results: User | None) -> None:
        self.scalar_results = deque(scalar_results)
        self.added: list[User] = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, _: Any) -> User | None:
        return self.scalar_results.popleft() if self.scalar_results else None

    def add(self, user: User) -> None:
        self.added.append(user)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, user: User) -> None:
        now = datetime.now(UTC)
        user.id = user.id or uuid4()
        user.created_at = user.created_at or now
        user.updated_at = user.updated_at or now


def make_user(
    *,
    role: UserRole = UserRole.CITIZEN,
    active: bool = True,
    password: str = "Correct-Password-123",
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        password_hash=hash_password(password),
        role=role,
        is_active=active,
        created_at=now,
        updated_at=now,
    )


def make_application(session: FakeSession):
    application = create_app(TEST_SETTINGS)

    async def override_session():
        yield session

    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    return application


async def request(application, method: str, url: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        return await client.request(method, url, **kwargs)


def test_valid_login_returns_access_token() -> None:
    user = make_user()
    application = make_application(FakeSession(user))

    response = asyncio.run(
        request(
            application,
            "POST",
            "/auth/login",
            data={"username": user.email, "password": "Correct-Password-123"},
        )
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    assert response.json()["access_token"]


def test_invalid_password_returns_generic_unauthorized_response() -> None:
    user = make_user()
    application = make_application(FakeSession(user))

    response = asyncio.run(
        request(
            application,
            "POST",
            "/auth/login",
            data={"username": user.email, "password": "Wrong-Password-456"},
        )
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_duplicate_email_registration_is_rejected() -> None:
    existing_user = make_user()
    session = FakeSession(existing_user)
    application = make_application(session)

    response = asyncio.run(
        request(
            application,
            "POST",
            "/auth/register/citizen",
            json={
                "name": "Another Citizen",
                "email": "TEST@example.com",
                "password": "Another-Password-123",
            },
        )
    )

    assert response.status_code == 409
    assert not session.added


def test_current_profile_requires_authentication() -> None:
    application = make_application(FakeSession())

    response = asyncio.run(request(application, "GET", "/auth/me"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_profile_returns_authenticated_user() -> None:
    user = make_user()
    application = make_application(FakeSession(user))
    token = create_access_token(user, TEST_SETTINGS)

    response = asyncio.run(
        request(
            application,
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["role"] == "CITIZEN"
    assert "password_hash" not in response.json()


def test_inactive_account_is_rejected_for_login_and_current_user() -> None:
    user = make_user(active=False)
    login_application = make_application(FakeSession(user))

    login_response = asyncio.run(
        request(
            login_application,
            "POST",
            "/auth/login",
            data={"username": user.email, "password": "Correct-Password-123"},
        )
    )

    profile_application = make_application(FakeSession(user))
    token = create_access_token(user, TEST_SETTINGS)
    profile_response = asyncio.run(
        request(
            profile_application,
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    assert login_response.status_code == 403
    assert profile_response.status_code == 403
    assert profile_response.json() == {"detail": "Account is inactive"}


def test_role_restricted_dependency_denies_wrong_role_and_allows_admin() -> None:
    police_user = make_user(role=UserRole.POLICE)
    police_application = make_application(FakeSession(police_user))

    @police_application.get("/_test/admin")
    async def admin_route(_: User = Depends(require_admin)) -> dict[str, bool]:
        return {"allowed": True}

    police_token = create_access_token(police_user, TEST_SETTINGS)
    denied = asyncio.run(
        request(
            police_application,
            "GET",
            "/_test/admin",
            headers={"Authorization": f"Bearer {police_token}"},
        )
    )

    admin_user = make_user(role=UserRole.ADMIN)
    admin_application = make_application(FakeSession(admin_user))

    @admin_application.get("/_test/admin")
    async def second_admin_route(_: User = Depends(require_admin)) -> dict[str, bool]:
        return {"allowed": True}

    admin_token = create_access_token(admin_user, TEST_SETTINGS)
    allowed = asyncio.run(
        request(
            admin_application,
            "GET",
            "/_test/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    )

    assert denied.status_code == 403
    assert denied.json() == {"detail": "Insufficient permissions"}
    assert allowed.status_code == 200
    assert allowed.json() == {"allowed": True}
