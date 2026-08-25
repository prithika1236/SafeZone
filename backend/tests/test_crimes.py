"""Crime-management validation, authorization, and ingestion tests."""

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.security import create_access_token
from app.database.dependencies import get_db_session
from app.main import create_app
from app.models.enums import UserRole
from app.schemas.crime import CrimeBulkRequest, CrimeCreate
from app.services.crime_service import CrimeCSVError, bulk_ingest, ingest_crime_csv, parse_crime_csv
from tests.test_auth_api import TEST_SETTINGS, make_user


def valid_crime(**overrides: Any) -> dict[str, Any]:
    values = {"crime_type": "THEFT", "severity": 3, "latitude": 12.9716,
              "longitude": 77.5946, "occurred_at": "2026-08-24T10:00:00+05:30",
              "reported_at": "2026-08-24T11:00:00+05:30",
              "source_reference": "POLICE-2026-001"}
    values.update(overrides)
    return values


@pytest.mark.parametrize(("field", "value"),
                         [("severity", 0), ("severity", 6), ("latitude", 91), ("longitude", -181)])
def test_crime_schema_rejects_boundaries(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        CrimeCreate.model_validate(valid_crime(**{field: value}))


def test_crime_schema_rejects_naive_and_reversed_times() -> None:
    with pytest.raises(ValidationError):
        CrimeCreate.model_validate(valid_crime(occurred_at="2026-08-24T10:00:00"))
    with pytest.raises(ValidationError):
        CrimeCreate.model_validate(valid_crime(occurred_at="2026-08-24T12:00:00+05:30"))


class ScalarRows:
    def __init__(self, values: list[str]) -> None:
        self.values = values
    def all(self) -> list[str]:
        return self.values


class BulkSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0
    async def scalars(self, _: Any) -> ScalarRows:
        return ScalarRows(["EXISTING"])
    def add(self, value: Any) -> None:
        self.added.append(value)
    async def commit(self) -> None:
        self.commits += 1


def test_bulk_reports_duplicates_and_malformed_rows() -> None:
    session = BulkSession()
    request = CrimeBulkRequest(rows=[valid_crime(source_reference="NEW"),
        valid_crime(source_reference="EXISTING"), valid_crime(source_reference="NEW"),
        valid_crime(source_reference=None), valid_crime(latitude=100, source_reference="BAD")])
    result = asyncio.run(bulk_ingest(session, request))
    assert result.total_rows == 5
    assert result.accepted == 1
    assert result.duplicates == ["EXISTING", "NEW"]
    assert [item.row for item in result.rejected] == [3, 4]
    assert len(session.added) == 1 and session.commits == 1


async def call_list(role: UserRole | None):
    application = create_app(TEST_SETTINGS)
    user = make_user(role=role) if role else None
    class AuthSession:
        async def scalar(self, _: Any):
            return user
    async def override_session():
        yield AuthSession()
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    headers = ({"Authorization": f"Bearer {create_access_token(user, TEST_SETTINGS)}"}
               if user else {})
    async with AsyncClient(transport=ASGITransport(app=application),
                           base_url="http://testserver") as client:
        return await client.get("/crimes", headers=headers)


def test_crimes_reject_unauthenticated_and_citizen_access() -> None:
    assert asyncio.run(call_list(None)).status_code == 401
    assert asyncio.run(call_list(UserRole.CITIZEN)).status_code == 403


def test_csv_parser_requires_headers_and_reports_partial_failures() -> None:
    with pytest.raises(CrimeCSVError, match="Missing required CSV columns"):
        parse_crime_csv(b"crime_type,severity\nTHEFT,3\n")

    content = (
        "source_reference,crime_type,severity,latitude,longitude,occurred_at,reported_at,ward,area,status\n"
        "NEW,THEFT,3,12.9,77.5,2026-08-24T10:00:00+05:30,2026-08-24T11:00:00+05:30,W1,A1,REPORTED\n"
        "BAD,THEFT,9,12.9,77.5,2026-08-24T10:00:00+05:30,2026-08-24T11:00:00+05:30,W1,A1,REPORTED\n"
    ).encode()
    session = BulkSession()
    result = asyncio.run(ingest_crime_csv(session, content))

    assert result.total_rows == 2
    assert result.accepted == 1
    assert [item.row for item in result.rejected] == [1]


async def call_csv_as_citizen():
    application = create_app(TEST_SETTINGS)
    user = make_user(role=UserRole.CITIZEN)
    class AuthSession:
        async def scalar(self, _: Any):
            return user
    async def override_session():
        yield AuthSession()
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    token = create_access_token(user, TEST_SETTINGS)
    async with AsyncClient(transport=ASGITransport(app=application),
                           base_url="http://testserver") as client:
        return await client.post(
            "/crimes/import/csv",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("incidents.csv", b"x", "text/csv")},
        )


def test_csv_upload_is_admin_only() -> None:
    assert asyncio.run(call_csv_as_citizen()).status_code == 403
