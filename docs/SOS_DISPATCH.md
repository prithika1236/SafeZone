# SOS emergency dispatch

Stage 13 implements operational emergency dispatch independently of strategic PRP optimization. Creating an SOS never invokes candidate generation, risk scoring, or PRP optimization.

## Lifecycle

`PENDING -> ASSIGNED -> ACCEPTED -> EN_ROUTE -> ARRIVED -> RESOLVED`

The request remains `PENDING` when no eligible responder exists. When a responder is selected in the same transaction it becomes `ASSIGNED`. Police transitions must follow the sequence exactly. A citizen may cancel only while `PENDING` or `ASSIGNED`; cancellation is rejected after officer acceptance.

## Dispatch selection

Eligible units must have a current location, an active shift assignment, a dispatch-capable unit state, and no other active SOS. Candidate rows are locked with PostgreSQL `FOR UPDATE SKIP LOCKED`, and partial unique indexes prevent concurrent active emergencies from owning the same patrol or citizen.

Candidates are bounded by `SOS_DISPATCH_RADIUS_METERS` and `SOS_DISPATCH_CANDIDATE_LIMIT`. If routing is configured and succeeds for every candidate, the shortest road-route distance wins. If routing is absent or any route lookup fails, all candidates are compared consistently by PostGIS straight-line geography distance. Route ETA is never invented from straight-line distance. Stable UUID ordering breaks ties.

## Privacy

Police assigned to the incident receive the emergency coordinate needed for response. Citizen responses contain status, approximate responder distance, optional route ETA, and lifecycle timestamps only. They contain no patrol-unit identifier, exact responder coordinate, or PRP location.

The mobile client polls the status endpoint every ten seconds while a request is active. Push notifications or WebSockets are intentionally outside Stage 13.
