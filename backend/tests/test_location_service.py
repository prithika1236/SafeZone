"""Geospatial query, privacy DTO, and routing-adapter tests."""

import asyncio
import math
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.schemas.location import BoundingBox, Coordinate, IncidentMapDTO, OperationalPatrolMapDTO
from app.services.location_service import (
    OSRMRoutingClient,
    RouteNotFoundError,
    RoutingUnavailableError,
    geodesic_distance_meters,
    incidents_in_bounding_box,
    incidents_within_radius,
    nearest_available_patrol,
    validate_coordinate,
    validate_radius,
)


class EmptyResult:
    def all(self) -> list[Any]:
        return []


class CaptureSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> EmptyResult:
        self.statements.append(statement)
        return EmptyResult()


def compiled(statement: Any) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_coordinate_and_radius_validation() -> None:
    assert validate_coordinate(12.9, 77.5) == Coordinate(latitude=12.9, longitude=77.5)
    for latitude, longitude in ((91, 0), (0, 181), (math.nan, 0)):
        with pytest.raises((ValidationError, ValueError)):
            validate_coordinate(latitude, longitude)
    for radius in (0, -1, math.inf, math.nan):
        with pytest.raises(ValueError):
            validate_radius(radius)


def test_haversine_distance_reference_values_and_symmetry() -> None:
    origin = Coordinate(latitude=0, longitude=0)
    one_degree_east = Coordinate(latitude=0, longitude=1)
    distance = geodesic_distance_meters(origin, one_degree_east)

    assert geodesic_distance_meters(origin, origin) == pytest.approx(0)
    assert distance == pytest.approx(111_195.08, abs=1)
    assert geodesic_distance_meters(one_degree_east, origin) == pytest.approx(distance)


def test_nearby_incident_query_uses_postgis_geography_distance() -> None:
    session = CaptureSession()
    result = asyncio.run(
        incidents_within_radius(session, Coordinate(latitude=12.9, longitude=77.5), 3000)
    )
    sql = compiled(session.statements[0])

    assert result == []
    assert "ST_DWithin" in sql
    assert "ST_Distance" in sql
    assert "geography(POINT,4326)" in sql


def test_nearest_available_patrol_uses_latest_location_and_availability() -> None:
    session = CaptureSession()
    result = asyncio.run(
        nearest_available_patrol(session, Coordinate(latitude=12.9, longitude=77.5), 5000)
    )
    sql = compiled(session.statements[0])

    assert result is None
    assert "row_number() OVER" in sql
    assert "patrol_units.status IN" in sql
    assert "ST_DWithin" in sql
    assert "LIMIT" in sql


def test_bounding_box_validation_and_postgis_query() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(south=13, west=77, north=12, east=78)
    bounds = BoundingBox(south=12, west=77, north=13, east=78)
    session = CaptureSession()
    assert asyncio.run(incidents_in_bounding_box(session, bounds)) == []
    assert "ST_MakeEnvelope" in compiled(session.statements[0])
    assert "ST_Intersects" in compiled(session.statements[0])


def test_map_dtos_exclude_sensitive_internal_fields() -> None:
    assert "source_reference" not in IncidentMapDTO.model_fields
    assert "password_hash" not in IncidentMapDTO.model_fields
    assert "location_history" not in OperationalPatrolMapDTO.model_fields
    assert "officer" not in OperationalPatrolMapDTO.model_fields


def test_osrm_adapter_returns_road_route_metrics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/route/v1/driving/77.5,12.9;77.6,13.0" in str(request.url)
        return httpx.Response(
            200, request=request, json={"code": "Ok", "routes": [{"distance": 15400.5, "duration": 1260.0}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = OSRMRoutingClient("http://routing.internal", client=client)
    estimate = asyncio.run(
        router.estimate_route(
            Coordinate(latitude=12.9, longitude=77.5),
            Coordinate(latitude=13.0, longitude=77.6),
        )
    )
    asyncio.run(client.aclose())

    assert estimate.distance_meters == 15400.5
    assert estimate.duration_seconds == 1260.0
    assert estimate.provider == "osrm-compatible"


@pytest.mark.parametrize(
    "handler,error",
    [
        (lambda request: httpx.Response(503, request=request), RoutingUnavailableError),
        (
            lambda request: httpx.Response(200, request=request, json={"code": "NoRoute", "routes": []}),
            RouteNotFoundError,
        ),
    ],
)
def test_osrm_adapter_reports_failures_without_fallback(handler, error) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = OSRMRoutingClient("http://routing.internal", client=client)
    with pytest.raises(error):
        asyncio.run(
            router.estimate_route(
                Coordinate(latitude=12.9, longitude=77.5),
                Coordinate(latitude=13.0, longitude=77.6),
            )
        )
    asyncio.run(client.aclose())


def test_osrm_timeout_is_explicitly_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    router = OSRMRoutingClient("http://routing.internal", client=client)
    with pytest.raises(RoutingUnavailableError):
        asyncio.run(
            router.estimate_route(
                Coordinate(latitude=12.9, longitude=77.5),
                Coordinate(latitude=13.0, longitude=77.6),
            )
        )
    asyncio.run(client.aclose())
