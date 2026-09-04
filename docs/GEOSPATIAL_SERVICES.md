# Geospatial and routing services

Stage 5 centralizes WGS84 coordinate validation, distance conventions, PostGIS queries, privacy-scoped map DTOs, and road-routing access in `backend/app/services/location_service.py`.

## Distance conventions

- In-memory straight-line distance uses the haversine formula and returns meters.
- Database proximity uses PostGIS `geography(Point,4326)` with `ST_DWithin` and `ST_Distance`, also in meters.
- Straight-line proximity is not an estimated driving route.
- Road distance and duration are returned only by the configured OSRM-compatible adapter.

## Spatial queries

The service can query incidents and the latest known patrol-unit locations within a positive radius or non-antimeridian bounding box. Nearest-patrol lookup considers only units whose persisted status is `AVAILABLE`; it does not reserve, assign, or dispatch the unit.

Patrol queries derive current position from each unit's newest `location_updates` record. No duplicate current-coordinate field is introduced.

## Routing

`OSRMRoutingClient` depends on the `RoutingClient` protocol and obtains its base URL and timeout from configuration. A private or managed OSRM-compatible deployment can replace the local endpoint without changing business logic. Timeouts, network errors, HTTP errors, malformed responses, and missing routes raise typed errors. The service never fabricates road distance or ETA from straight-line proximity.

Configuration:

```env
ROUTING_SERVICE_BASE_URL=http://localhost:5000
ROUTING_SERVICE_TIMEOUT_SECONDS=5
DEFAULT_PROXIMITY_RADIUS_METERS=3000
```

## Privacy

`IncidentMapDTO` excludes ingestion references and internal audit data. `OperationalPatrolMapDTO` contains precise operational location and is explicitly restricted to authorized ADMIN/POLICE consumers; it excludes officer identity and location history. No citizen map endpoint is introduced in this stage.
