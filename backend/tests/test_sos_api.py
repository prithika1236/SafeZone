"""SOS API authentication, privacy, and route-scope tests."""

import asyncio

from app.core.security import create_access_token
from app.models.enums import UserRole
from app.schemas.sos import CitizenSOSResponse
from tests.test_auth_api import TEST_SETTINGS, FakeSession, make_application, make_user, request


def authenticated(role: UserRole, method: str, path: str, **kwargs):
    user = make_user(role=role)
    token = create_access_token(user, TEST_SETTINGS)
    return asyncio.run(request(
        make_application(FakeSession(user)), method, path,
        headers={"Authorization": f"Bearer {token}"}, **kwargs,
    ))


def test_sos_creation_requires_authentication() -> None:
    response = asyncio.run(request(
        make_application(FakeSession()), "POST", "/sos", json={"latitude": 9.35, "longitude": 78.51}
    ))
    assert response.status_code == 401


def test_police_cannot_create_citizen_sos() -> None:
    response = authenticated(
        UserRole.POLICE, "POST", "/sos", json={"latitude": 9.35, "longitude": 78.51}
    )
    assert response.status_code == 403


def test_citizen_cannot_read_police_dispatch() -> None:
    assert authenticated(UserRole.CITIZEN, "GET", "/sos/police/current").status_code == 403


def test_citizen_contract_never_contains_prp_or_exact_location() -> None:
    fields = CitizenSOSResponse.model_fields
    assert "emergency_location" not in fields
    assert "assigned_patrol_unit_id" not in fields
    assert all("prp" not in name for name in fields)


def test_openapi_contains_sos_lifecycle_without_optimization_route() -> None:
    paths = make_application(FakeSession()).openapi()["paths"]
    expected = {
        "/sos", "/sos/current", "/sos/{sos_id}/cancel", "/sos/police/current",
        "/sos/{sos_id}/accept", "/sos/{sos_id}/en-route",
        "/sos/{sos_id}/arrive", "/sos/{sos_id}/resolve",
    }
    assert expected <= set(paths)
    assert all("optim" not in path for path in expected)
