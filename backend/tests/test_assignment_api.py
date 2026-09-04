"""Role-boundary tests for patrol assignment endpoints."""

import asyncio

from app.core.security import create_access_token
from app.models.enums import UserRole
from tests.test_auth_api import TEST_SETTINGS, FakeSession, make_application, make_user, request


def authenticated_get(role: UserRole, path: str):
    user = make_user(role=role)
    return asyncio.run(
        request(
            make_application(FakeSession(user)),
            "GET",
            path,
            headers={"Authorization": f"Bearer {create_access_token(user, TEST_SETTINGS)}"},
        )
    )


def test_assignment_endpoints_require_authentication() -> None:
    response = asyncio.run(
        request(make_application(FakeSession()), "GET", "/patrols/assignments")
    )
    assert response.status_code == 401


def test_citizen_cannot_inspect_operational_assignments() -> None:
    assert authenticated_get(UserRole.CITIZEN, "/patrols/assignments").status_code == 403


def test_police_cannot_use_admin_assignment_list() -> None:
    assert authenticated_get(UserRole.POLICE, "/patrols/assignments").status_code == 403


def test_admin_cannot_use_police_current_assignment_endpoint() -> None:
    assert authenticated_get(UserRole.ADMIN, "/patrols/assignments/current").status_code == 403


def test_openapi_contains_admin_and_police_workflows() -> None:
    paths = make_application(FakeSession()).openapi()["paths"]
    expected = {
        "/patrols/assignments/automatic",
        "/patrols/assignments",
        "/patrols/assignments/current",
        "/patrols/assignments/{assignment_id}",
        "/patrols/assignments/{assignment_id}/override",
        "/patrols/assignments/{assignment_id}/cancel",
        "/patrols/assignments/{assignment_id}/acknowledge",
        "/patrols/assignments/{assignment_id}/arrive",
        "/patrols/assignments/{assignment_id}/complete",
    }
    assert expected <= set(paths)

