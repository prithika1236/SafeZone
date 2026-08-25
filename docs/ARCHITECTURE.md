# SafeZone Architecture

## System purpose

**SafeZone: AI-Assisted Intelligent Police Patrol Deployment and Emergency Response System** supports strategic patrol positioning and real-time emergency response. It uses explainable risk scoring and optimization; it must not claim predictive machine learning in the initial version.

The repository is a monorepo containing exactly one backend, one role-based Flutter mobile application, and one React/Vite administration dashboard. The backend is the authority for authentication, authorization, domain rules, operational state, privacy enforcement, scoring, optimization, and dispatch.

## System components

### Citizen application

The Citizen interface is a role-based module in `mobile/safezone_app`, not a separate Flutter application. It supports citizen authentication and approved citizen workflows, including creating an SOS and observing its response status. It may display approximate responder distance and estimated arrival information when available. It must never receive exact PRPs or precise operational patrol deployment information.

### Police application

The Police interface is another role-based module in the same Flutter application. It supports authorized officer workflows such as availability, assigned PRPs/patrol duties, SOS assignment acceptance, and response status updates. Access to operational PRP data is limited by authenticated role and assignment/permission policy.

### Admin dashboard

The dashboard is one React + Vite application in `admin-dashboard`. It provides authorized administration, crime-data management, operational map views, risk/optimization controls, patrol oversight, and approved analytics. Maps use Leaflet/React Leaflet with OpenStreetMap.

### Backend API

The FastAPI backend in `backend/app` exposes REST APIs for normal operations. WebSocket connections may be added only for genuinely live SOS or location/status updates. Route handlers validate and authorize requests, delegate business logic to services/optimization modules, and serialize responses; they do not contain domain or database logic.

### Database

PostgreSQL with PostGIS stores normalized domain and geospatial data. SQLAlchemy 2.x provides ORM/data access architecture, and Alembic owns schema migrations. Tables are introduced only as their implementation stages require them.

The planned primary domain entities are:

- `users`
- `police_officers`
- `crime_incidents`
- `sos_requests`
- `patrol_units`
- `prp_locations`
- `patrol_assignments`
- `location_updates`
- `emergency_contacts`
- `risk_scores`
- `optimization_runs`

### External infrastructure abstractions

- Routing is accessed through an OSRM-compatible interface configured by environment. Business logic must not depend on a single public OSRM server.
- Notifications are accessed through a provider-neutral notification service with a Firebase Cloud Messaging adapter.
- Credentials, endpoints, timeouts, risk parameters, coverage radius, and infrastructure settings are environment-driven and documented safely in `.env.example`.

## Core strategic data flow

The core intelligence pipeline is:

```text
Crime Data
  -> validation and preprocessing
  -> explainable risk scoring
  -> candidate patrol location generation
  -> coverage calculation
  -> dynamic PRP optimization
  -> patrol allocation
  -> authorized operational views
```

Risk scoring initially combines configurable contributions for crime frequency, severity, recency, and time of day. Recency supports exponential time decay:

```text
recency_weight = exp(-lambda * age_in_days)
```

All weights and decay settings are configurable. Scores are normalized to a practical range such as 0–1 using a deterministic method with defined edge-case behavior.

Candidate locations are inputs to optimization, not deployed PRPs. The optimizer selects no more PRPs than eligible available patrol units and maximizes total weighted risk covered within a configurable radius. The prototype radius defaults to 3 km, but business logic must obtain it from validated configuration or policy rather than repeating a hard-coded value.

The coverage objective prevents a simplistic top-N selection that could waste patrol capacity on overlapping high-risk points. Google OR-Tools is the approved optimization layer where appropriate. Optimization inputs, configuration, solver status, objective, and results must be auditable.

## PRP and SOS are distinct processes

### PRP optimization: strategic positioning

A Patrol Response Point is a dynamically generated recommended patrol position for a specific shift or operational period. It is not a permanent police station. PRPs can change based on recent crime information, severity, time-of-day risk, available units, and configured coverage radius.

PRP processing operates on aggregated risk and candidate locations to improve area coverage. Its output is used by authorized administrators and police operations for planned positioning.

### SOS dispatch: real-time response

SOS dispatch handles a specific emergency and must not invoke full PRP optimization. Its flow is:

```text
Citizen presses SOS
  -> citizen location is obtained and validated
  -> SOS request is created
  -> nearest suitable AVAILABLE patrol is reserved and assigned
  -> assigned officer is notified
  -> officer accepts
  -> EN_ROUTE
  -> ARRIVED
  -> RESOLVED
```

Dispatch considers availability, suitability, and distance or route policy. Reservation and lifecycle changes must be concurrency-safe and auditable. If no suitable unit is available or routing fails, the system must return a meaningful operational state without triggering strategic re-optimization.

## Role permissions

Backend authorization is authoritative; hiding controls in a client is never sufficient.

| Capability | ADMIN | POLICE | CITIZEN |
| --- | --- | --- | --- |
| Authenticate and manage own permitted profile data | Yes | Yes | Yes |
| Manage users/roles under approved policy | Yes | No | No |
| Manage crime data | Yes | Only if explicitly granted by policy | No |
| Configure/run PRP optimization | Yes | Only if explicitly granted by policy | No |
| View operational PRPs | Yes | Only authorized operational scope | Never |
| View patrol allocations | Yes | Own/authorized operational scope | Never |
| Set police availability/status | Oversight only | Own authorized status | No |
| Create a citizen SOS | No by role default | No by role default | Yes |
| Accept/update an assigned SOS response | Oversight only | Assigned/authorized SOS | No |
| View SOS operational details | Authorized oversight | Assigned/authorized scope | Own SOS, privacy-filtered |
| View approved analytics | Yes | Only if explicitly granted and scoped | No operational analytics |

Permissions that are not yet implemented must default to denied. Any later refinement must preserve the citizen privacy boundary and least-privilege access.

## Privacy rule

Citizens must not receive exact PRP locations, precise patrol deployment details, police-only location streams, optimization inputs/outputs, or operational map layers. Citizen-safe responses may include:

- the status of their own SOS response;
- confirmation that a patrol has been assigned;
- approximate responder distance;
- estimated arrival information when available.

Privacy must be enforced before serialization through role-specific schemas and authorized services, not solely through mobile UI filtering. The same boundary applies to REST, WebSocket, notifications, logs, analytics, caches, exports, and error messages. Location collection and retention must be limited to the approved operational purpose.

## Frozen technology stack

| Layer | Approved technology |
| --- | --- |
| Mobile | Flutter / Dart; one role-based Citizen and Police app |
| Mobile maps | `flutter_map` with OpenStreetMap |
| Admin dashboard | React + Vite |
| Dashboard maps | Leaflet / React Leaflet with OpenStreetMap |
| Backend | Python + FastAPI |
| Database | PostgreSQL + PostGIS |
| ORM and migrations | SQLAlchemy 2.x architecture + Alembic |
| Validation | Pydantic |
| Optimization/analytics | Python, NumPy, Pandas, Google OR-Tools |
| Predictive ML | Scikit-learn only later for a genuine approved requirement; not in the initial risk model |
| Routing | Configurable OSRM-compatible abstraction |
| Authentication | JWT with secure password hashing and role-based authorization |
| Notifications | Firebase Cloud Messaging abstraction |
| Communication | REST normally; WebSocket only for genuinely live SOS/location state |
| Development | Git, GitHub, VS Code, Postman |
| Deployment | Docker and Docker Compose during deployment preparation |

Changing this stack or introducing a competing framework requires explicit approval.

## Major backend module responsibilities

### API layer: `backend/app/api/`

- `auth.py`: Authentication endpoints and public authentication contracts; delegates credential/token logic.
- `crimes.py`: Authorized crime-data endpoints; delegates validation-aware domain operations and persistence.
- `sos.py`: Citizen-safe SOS creation/status and authorized police lifecycle endpoints; delegates dispatch.
- `patrols.py`: Patrol availability, status, and assignment endpoints.
- `prp.py`: Authorized PRP generation/optimization result endpoints; never citizen-exposed.
- `admin.py`: Administrator-only orchestration, configuration views, and approved analytics endpoints.

API handlers remain thin: request parsing, authorization, service invocation, and response serialization only.

### Models: `backend/app/models/`

SQLAlchemy domain persistence models and relationships. Models use normalized structures, explicit constraints, appropriate indexes, auditable timestamps/state, and PostGIS spatial types. They must not be duplicated as ad hoc models inside route or service files.

### Schemas: `backend/app/schemas/`

Pydantic request, response, internal transfer, and validation schemas. Separate role-appropriate responses prevent sensitive operational fields from reaching citizen clients. Public schema evolution preserves backward compatibility where practical.

### Services: `backend/app/services/`

- `risk_service.py`: Coordinates risk-data retrieval, scoring execution, normalization/persistence policy, and explainable results. Mathematical primitives remain in the optimization layer.
- `dispatch_service.py`: Performs concurrency-safe SOS patrol selection, reservation, assignment, and permitted lifecycle transitions. It does not invoke PRP optimization.
- `location_service.py`: Owns coordinate validation, geospatial queries/calculations, distance conventions, and OSRM-compatible route access.
- `notification_service.py`: Defines provider-neutral notification behavior and delegates delivery to configured adapters such as FCM without coupling domain transactions to a provider.

Additional services may be added only for a cohesive, genuinely distinct responsibility. Services contain business workflows and must not depend on HTTP route objects.

### Optimization: `backend/app/optimization/`

- `risk_scoring.py`: Pure, explainable contribution calculations, time decay, weighted composition, and normalization.
- `candidate_generator.py`: Generates and spatially consolidates traceable candidate patrol positions.
- `coverage.py`: Builds distance/coverage relationships for a supplied configurable radius.
- `prp_optimizer.py`: Formulates and solves weighted maximum coverage within patrol-capacity constraints using OR-Tools where appropriate.
- `assignment.py`: Assigns selected PRPs to eligible patrol units under defined constraints; separate from emergency dispatch.

Optimization functions should use typed inputs/outputs, remain deterministic where applicable, and expose status/explanation rather than hiding failure or approximation.

### Database: `backend/app/database/`

Owns engine and async session creation, declarative metadata, transaction/session lifecycle, and database initialization conventions. Alembic remains the authority for schema changes. Repositories or query modules may live here or in cohesive domain submodules, but database operations must not be embedded in routes.

### Core: `backend/app/core/`

Owns validated environment settings, security primitives, shared authorization dependencies, structured logging configuration, application exceptions, and other cross-cutting infrastructure. It must not become a dumping ground for domain logic.

### Application entry point: `backend/app/main.py`

Creates and configures the FastAPI application, lifespan resources, middleware, exception handling, and router registration. It must not perform domain work or contain feature implementations.

## Cross-cutting architecture rules

- Validate all external input at system boundaries and enforce domain invariants in services/models as appropriate.
- Use typed Python and async FastAPI/database patterns where they improve correctness and latency without needless complexity.
- Use structured logging; redact credentials, tokens, citizen locations, and sensitive operational details.
- Avoid repeated queries, polling, recomputation, and blocking provider calls in critical request transactions.
- Maintain clean separation among routes, schemas, services, persistence, and optimization.
- Update tests whenever behavior changes and never silently ignore a failing check.
- Preserve public API compatibility when modifying an existing contract.
- Never create duplicate applications, services, implementations, or suffix variants such as `_new`, `_final`, `_updated`, or `_v2`.

## Current repository baseline

At the time this architecture document was created, the repository contained only Git metadata. No Python, database, Flutter, React, dependency, test, environment, or application files existed. Therefore, there were no structural or implementation conflicts with the frozen architecture; the required application structure was simply not yet initialized.
