import asyncio

from app.core.security import create_access_token
from app.models.enums import UserRole
from tests.test_auth_api import TEST_SETTINGS, FakeSession, make_application, make_user, request


def test_police_location_requires_authentication() -> None:
    response = asyncio.run(request(make_application(FakeSession()), "POST", "/live/police/location", json={
        "latitude": 9.35, "longitude": 78.51,
    }))
    assert response.status_code == 401


def test_citizen_cannot_submit_police_location() -> None:
    user = make_user(role=UserRole.CITIZEN)
    token = create_access_token(user, TEST_SETTINGS)
    response = asyncio.run(request(
        make_application(FakeSession(user)), "POST", "/live/police/location",
        headers={"Authorization": f"Bearer {token}"},
        json={"latitude": 9.35, "longitude": 78.51},
    ))
    assert response.status_code == 403


def test_live_routes_are_narrowly_scoped() -> None:
    paths = make_application(FakeSession()).openapi()["paths"]
    assert "/live/police/location" in paths
    assert "/notifications/devices" in paths
    assert all("ws" not in path for path in paths)
