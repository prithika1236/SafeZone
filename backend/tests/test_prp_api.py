"""Authorization and transport tests for strategic PRP endpoints."""

import asyncio
from datetime import UTC, datetime

from app.core.security import create_access_token
from app.models.enums import UserRole
from tests.test_auth_api import TEST_SETTINGS, FakeSession, make_application, make_user, request


EMPTY_REQUEST = {
    "candidates": [],
    "demand_points": [],
    "available_patrol_count": 0,
    "coverage_radius_meters": 3000,
    "shift": {
        "start": datetime(2026, 9, 4, 8, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 9, 4, 16, tzinfo=UTC).isoformat(),
    },
}


def test_prp_preview_requires_authentication() -> None:
    response = asyncio.run(
        request(make_application(FakeSession()), "POST", "/prp/preview", json=EMPTY_REQUEST)
    )
    assert response.status_code == 401


def test_citizen_cannot_access_operational_prp_preview() -> None:
    citizen = make_user(role=UserRole.CITIZEN)
    response = asyncio.run(
        request(
            make_application(FakeSession(citizen)),
            "POST",
            "/prp/preview",
            json=EMPTY_REQUEST,
            headers={"Authorization": f"Bearer {create_access_token(citizen, TEST_SETTINGS)}"},
        )
    )
    assert response.status_code == 403


def test_admin_can_preview_without_persisting() -> None:
    admin = make_user(role=UserRole.ADMIN)
    session = FakeSession(admin)
    response = asyncio.run(
        request(
            make_application(session),
            "POST",
            "/prp/preview",
            json=EMPTY_REQUEST,
            headers={"Authorization": f"Bearer {create_access_token(admin, TEST_SETTINGS)}"},
        )
    )
    assert response.status_code == 200
    assert response.json()["solver_status"] == "NOT_RUN"
    assert session.commits == 0


def test_openapi_exposes_only_admin_prp_workflow_routes() -> None:
    application = make_application(FakeSession())
    document = application.openapi()
    expected = {
        "/prp/preview",
        "/prp/generate",
        "/prp/active",
        "/prp/runs/{run_id}",
        "/prp/runs/{run_id}/approve",
        "/prp/runs/{run_id}/activate",
    }
    assert expected <= set(document["paths"])
    assert not any("citizen" in path for path in document["paths"] if path.startswith("/prp"))

