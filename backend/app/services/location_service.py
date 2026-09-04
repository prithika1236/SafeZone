"""PostGIS proximity queries, geodesic calculations, and routing abstraction."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

import httpx
from geoalchemy2 import Geography, Geometry
from pydantic import AnyHttpUrl
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crime import CrimeIncident
from app.models.enums import CrimeIncidentStatus, PatrolUnitStatus
from app.models.location import LocationUpdate
from app.models.police import PatrolUnit
from app.schemas.location import (
    BoundingBox,
    Coordinate,
    IncidentMapDTO,
    OperationalPatrolMapDTO,
    RouteEstimate,
)

EARTH_MEAN_RADIUS_METERS = 6_371_008.8


class RoutingError(Exception):
    """Base error for road-routing failures."""


class RoutingUnavailableError(RoutingError):
    """The configured routing provider could not be reached successfully."""


class RouteNotFoundError(RoutingError):
    """The provider responded but supplied no usable road route."""


class RoutingClient(Protocol):
    async def estimate_route(self, origin: Coordinate, destination: Coordinate) -> RouteEstimate:
        """Return road-route distance and duration or raise a typed routing error."""


def validate_coordinate(latitude: float, longitude: float) -> Coordinate:
    """Validate WGS84 latitude/longitude and reject non-finite numbers."""
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("latitude and longitude must be finite")
    return Coordinate(latitude=latitude, longitude=longitude)


def validate_radius(radius_meters: float) -> float:
    """Require a finite, positive search radius expressed in meters."""
    if not math.isfinite(radius_meters) or radius_meters <= 0:
        raise ValueError("radius_meters must be a finite positive number")
    return radius_meters


def geodesic_distance_meters(origin: Coordinate, destination: Coordinate) -> float:
    """Calculate deterministic great-circle distance with the haversine formula."""
    latitude_1 = math.radians(origin.latitude)
    latitude_2 = math.radians(destination.latitude)
    latitude_delta = latitude_2 - latitude_1
    longitude_delta = math.radians(destination.longitude - origin.longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(longitude_delta / 2) ** 2
    )
    central_angle = 2 * math.atan2(math.sqrt(haversine), math.sqrt(max(0.0, 1 - haversine)))
    return EARTH_MEAN_RADIUS_METERS * central_angle


def _geography_point(coordinate: Coordinate):
    return cast(
        func.ST_SetSRID(func.ST_MakePoint(coordinate.longitude, coordinate.latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )


def _geometry_coordinates(location):
    geometry = cast(location, Geometry(geometry_type="POINT", srid=4326))
    return func.ST_X(geometry), func.ST_Y(geometry)


def _latest_patrol_locations():
    ranked = select(
        LocationUpdate.patrol_unit_id.label("patrol_unit_id"),
        LocationUpdate.location.label("location"),
        LocationUpdate.recorded_at.label("recorded_at"),
        func.row_number()
        .over(
            partition_by=LocationUpdate.patrol_unit_id,
            order_by=(LocationUpdate.recorded_at.desc(), LocationUpdate.id.desc()),
        )
        .label("location_rank"),
    ).subquery("ranked_patrol_locations")
    return (
        select(ranked.c.patrol_unit_id, ranked.c.location, ranked.c.recorded_at)
        .where(ranked.c.location_rank == 1)
        .subquery("latest_patrol_locations")
    )


async def incidents_within_radius(
    session: AsyncSession,
    center: Coordinate,
    radius_meters: float,
    *,
    statuses: Sequence[CrimeIncidentStatus] | None = None,
    limit: int = 500,
) -> list[IncidentMapDTO]:
    radius = validate_radius(radius_meters)
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    origin = _geography_point(center)
    longitude, latitude = _geometry_coordinates(CrimeIncident.location)
    distance = func.ST_Distance(CrimeIncident.location, origin)
    statement = select(
        CrimeIncident.id,
        CrimeIncident.crime_type,
        CrimeIncident.severity,
        CrimeIncident.occurred_at,
        CrimeIncident.status,
        longitude,
        latitude,
        distance.label("distance_meters"),
    ).where(func.ST_DWithin(CrimeIncident.location, origin, radius))
    if statuses:
        statement = statement.where(CrimeIncident.status.in_(statuses))
    rows = (
        await session.execute(
            statement
            .order_by(distance, CrimeIncident.id)
            .limit(limit)
        )
    ).all()
    return [
        IncidentMapDTO(
            id=row.id,
            crime_type=row.crime_type,
            severity=row.severity,
            occurred_at=row.occurred_at,
            status=row.status,
            location=Coordinate(latitude=row[6], longitude=row[5]),
            distance_meters=float(row.distance_meters),
        )
        for row in rows
    ]


def _patrol_map_query(*, statuses: Sequence[PatrolUnitStatus] | None = None):
    latest = _latest_patrol_locations()
    longitude, latitude = _geometry_coordinates(latest.c.location)
    statement = select(
        PatrolUnit.id.label("patrol_unit_id"),
        PatrolUnit.unit_identifier,
        PatrolUnit.display_name,
        PatrolUnit.status,
        latest.c.recorded_at,
        latest.c.location,
        longitude.label("longitude"),
        latitude.label("latitude"),
    ).join(latest, latest.c.patrol_unit_id == PatrolUnit.id)
    if statuses:
        statement = statement.where(PatrolUnit.status.in_(statuses))
    return statement, latest


async def patrol_units_within_radius(
    session: AsyncSession,
    center: Coordinate,
    radius_meters: float,
    *,
    statuses: Sequence[PatrolUnitStatus] | None = None,
    limit: int = 100,
) -> list[OperationalPatrolMapDTO]:
    radius = validate_radius(radius_meters)
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    origin = _geography_point(center)
    statement, latest = _patrol_map_query(statuses=statuses)
    distance = func.ST_Distance(latest.c.location, origin)
    rows = (
        await session.execute(
            statement.add_columns(distance.label("distance_meters"))
            .where(func.ST_DWithin(latest.c.location, origin, radius))
            .order_by(distance, PatrolUnit.id)
            .limit(limit)
        )
    ).all()
    return [_patrol_dto(row, float(row.distance_meters)) for row in rows]


async def nearest_available_patrol(
    session: AsyncSession,
    center: Coordinate,
    radius_meters: float,
) -> OperationalPatrolMapDTO | None:
    candidates = await patrol_units_within_radius(
        session,
        center,
        radius_meters,
        statuses=(PatrolUnitStatus.AVAILABLE,),
        limit=1,
    )
    return candidates[0] if candidates else None


def _patrol_dto(row, distance_meters: float | None = None) -> OperationalPatrolMapDTO:
    return OperationalPatrolMapDTO(
        patrol_unit_id=row.patrol_unit_id,
        unit_identifier=row.unit_identifier,
        display_name=row.display_name,
        status=row.status,
        recorded_at=row.recorded_at,
        location=Coordinate(latitude=row.latitude, longitude=row.longitude),
        distance_meters=distance_meters,
    )


async def incidents_in_bounding_box(
    session: AsyncSession, bounds: BoundingBox, *, limit: int = 500
) -> list[IncidentMapDTO]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    longitude, latitude = _geometry_coordinates(CrimeIncident.location)
    envelope = func.ST_MakeEnvelope(bounds.west, bounds.south, bounds.east, bounds.north, 4326)
    rows = (
        await session.execute(
            select(
                CrimeIncident.id,
                CrimeIncident.crime_type,
                CrimeIncident.severity,
                CrimeIncident.occurred_at,
                CrimeIncident.status,
                longitude,
                latitude,
            )
            .where(func.ST_Intersects(cast(CrimeIncident.location, Geometry("POINT", 4326)), envelope))
            .order_by(CrimeIncident.occurred_at.desc(), CrimeIncident.id)
            .limit(limit)
        )
    ).all()
    return [
        IncidentMapDTO(
            id=row.id,
            crime_type=row.crime_type,
            severity=row.severity,
            occurred_at=row.occurred_at,
            status=row.status,
            location=Coordinate(latitude=row[6], longitude=row[5]),
        )
        for row in rows
    ]


async def patrol_units_in_bounding_box(
    session: AsyncSession,
    bounds: BoundingBox,
    *,
    statuses: Sequence[PatrolUnitStatus] | None = None,
    limit: int = 100,
) -> list[OperationalPatrolMapDTO]:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    statement, latest = _patrol_map_query(statuses=statuses)
    envelope = func.ST_MakeEnvelope(bounds.west, bounds.south, bounds.east, bounds.north, 4326)
    rows = (
        await session.execute(
            statement.where(
                func.ST_Intersects(cast(latest.c.location, Geometry("POINT", 4326)), envelope)
            )
            .order_by(PatrolUnit.unit_identifier)
            .limit(limit)
        )
    ).all()
    return [_patrol_dto(row) for row in rows]


class OSRMRoutingClient:
    """Configurable adapter for an OSRM-compatible route service."""

    def __init__(
        self,
        base_url: str | AnyHttpUrl,
        *,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = str(base_url).rstrip("/")
        self._timeout = timeout_seconds
        self._client = client

    async def estimate_route(
        self, origin: Coordinate, destination: Coordinate
    ) -> RouteEstimate:
        coordinates = (
            f"{origin.longitude},{origin.latitude};"
            f"{destination.longitude},{destination.latitude}"
        )
        url = f"{self._base_url}/route/v1/driving/{coordinates}"
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            response = await client.get(
                url,
                params={"overview": "false", "steps": "false", "alternatives": "false"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            raise RoutingUnavailableError("Configured routing service is unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

        try:
            payload = response.json()
            route = payload["routes"][0]
            if payload.get("code") != "Ok":
                raise KeyError("non-Ok route code")
            distance = float(route["distance"])
            duration = float(route["duration"])
            if not math.isfinite(distance) or not math.isfinite(duration) or distance < 0 or duration < 0:
                raise ValueError("invalid route metrics")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RouteNotFoundError("Routing service returned no usable route") from exc
        return RouteEstimate(
            distance_meters=distance,
            duration_seconds=duration,
            provider="osrm-compatible",
        )
