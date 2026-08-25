# Crime-data management

Stage 4 provides validated, authorized management of operational crime incidents for later risk analysis. It does not calculate risk or expose raw crime records to citizens.

ADMIN and POLICE may create, list, retrieve, and update incidents. Only ADMIN may use `DELETE`; this sets the record status to `DISMISSED` instead of physically deleting it.

Endpoints are `POST /crimes`, `GET /crimes`, `GET /crimes/{incident_id}`, `PATCH /crimes/{incident_id}`, `DELETE /crimes/{incident_id}`, and `POST /crimes/bulk`.

ADMIN users may upload a UTF-8 CSV with `POST /crimes/import/csv`. The upload limit is configured with `CRIME_CSV_MAX_BYTES`. Required columns are `source_reference`, `crime_type`, `severity`, `latitude`, `longitude`, `occurred_at`, and `reported_at`; optional columns are `ward`, `area`, and `status`. The response reports total, accepted, duplicate, and rejected rows. Valid rows are retained even when other rows fail validation.

Listing provides bounded pagination and filters for category, severity, status, ward, area, occurrence time, and a four-coordinate geographic bounding box. API latitude/longitude values are validated and persisted once as PostGIS `geography(Point,4326)`.

Bulk requests accept at most 500 rows. Each row requires a stable `source_reference`; existing and within-file duplicates are reported without reinsertion, and malformed rows include their zero-based row number and reason. Sample files belong only in `data/sample/`, never in operational data.

The sample format is `data/sample/crime_incidents_sample.csv`. Its `SAMPLE-` record is illustrative and is never loaded automatically.
