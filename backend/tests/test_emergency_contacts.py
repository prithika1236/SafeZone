"""Emergency-contact validation and authorization boundary tests."""

import asyncio

from app.core.security import create_access_token
from app.models.enums import UserRole
from app.schemas.emergency_contact import EmergencyContactCreate
from tests.test_auth_api import TEST_SETTINGS, FakeSession, make_application, make_user, request


def test_contact_phone_validation_rejects_non_phone_text() -> None:
    try:
        EmergencyContactCreate(name="Mother", phone_number="not-a-phone")
    except ValueError:
        return
    raise AssertionError("invalid phone number was accepted")


def test_contacts_require_authentication() -> None:
    response = asyncio.run(request(make_application(FakeSession()), "GET", "/emergency-contacts"))
    assert response.status_code == 401


def test_police_cannot_access_citizen_contacts() -> None:
    user = make_user(role=UserRole.POLICE)
    token = create_access_token(user, TEST_SETTINGS)
    response = asyncio.run(
        request(
            make_application(FakeSession(user)),
            "GET",
            "/emergency-contacts",
            headers={"Authorization": f"Bearer {token}"},
        )
    )
    assert response.status_code == 403


def test_openapi_exposes_only_owner_contact_crud() -> None:
    paths = make_application(FakeSession()).openapi()["paths"]
    assert "/emergency-contacts" in paths
    assert "/emergency-contacts/{contact_id}" in paths
    assert "get" in paths["/emergency-contacts"]
    assert "post" in paths["/emergency-contacts"]
    assert "patch" in paths["/emergency-contacts/{contact_id}"]
    assert "delete" in paths["/emergency-contacts/{contact_id}"]
