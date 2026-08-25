# SafeZone Implementation Plan

## Purpose and governance

This document is the ordered implementation plan for **SafeZone: AI-Assisted Intelligent Police Patrol Deployment and Emergency Response System**. The repository is the single source of truth. Work must follow the frozen architecture, technology stack, behavior, privacy rules, and development rules established for the project.

Each stage must be completed and verified before work moves to a later stage unless a narrowly scoped interface is necessary for the current stage. Existing modules must be extended in place; duplicate implementations, alternate applications, and experimental suffix files are prohibited. Every stage begins with repository inspection and ends with relevant automated checks and a report of results.

Configuration values, including coverage radius and risk weights, must come from validated configuration rather than being repeated as constants in business logic. Secrets must come from environment variables, with safe placeholders documented in `.env.example`.

## 1. Repository foundation

**Goal:** Establish the approved monorepo structure and minimal, runnable project foundations without implementing domain features.

**Modules involved:** Repository root; `backend/`; `backend/app/`; `backend/tests/`; `mobile/safezone_app/`; `admin-dashboard/`; `data/raw/`; `data/processed/`; `data/sample/`; `notebooks/`; `docs/`; `scripts/`; root configuration and documentation files.

**Dependencies:** Approved folder structure; supported Python, Flutter/Dart, Node.js, and Git toolchains; frozen technology stack.

**Acceptance criteria:**

- Required top-level structure exists exactly as approved, with no alternate backend, mobile, or dashboard application.
- Minimal FastAPI, Flutter, and React/Vite projects can be started or built without domain behavior.
- `.gitignore`, `.env.example`, and `README.md` describe local setup without containing credentials.
- Dependency files use only required packages and establish compatible version constraints.
- Structured logging and typed configuration conventions are established for later stages.

**Tests required:** Backend import/startup smoke test; Flutter analyze/test baseline; React lint/build baseline; repository structure and secret-scan checks.

## 2. Database foundation

**Goal:** Establish asynchronous SQLAlchemy 2.x and Alembic infrastructure for PostgreSQL/PostGIS, introducing only the entities required by the current stage.

**Modules involved:** `backend/app/database/`; `backend/app/models/`; Alembic configuration and migrations; `backend/app/core/` configuration; backend test fixtures.

**Dependencies:** Repository foundation; PostgreSQL with PostGIS; SQLAlchemy 2.x; Alembic; async PostgreSQL driver; Pydantic settings.

**Acceptance criteria:**

- Database URL and pool settings are validated environment configuration.
- Async engine, session lifecycle, declarative base, and migration workflow are defined once.
- PostGIS extension support and spatial column conventions are migration-managed.
- Transactions and session cleanup behave correctly on success and failure.
- No future domain tables are created before their implementing stage requires them.

**Tests required:** Configuration validation tests; database connection/session integration tests; migration upgrade/downgrade test against a disposable PostGIS database; transaction rollback test.

## 3. Authentication and RBAC

**Goal:** Implement secure JWT authentication and authorization for `ADMIN`, `POLICE`, and `CITIZEN` while preserving a stable public API.

**Modules involved:** `backend/app/api/auth.py`; user and police-officer models as required; authentication schemas; security and dependency modules in `backend/app/core/`; authentication service layer; backend tests.

**Dependencies:** Database foundation; secure password-hashing library; JWT library; validated secret, issuer, audience, and expiry configuration.

**Acceptance criteria:**

- Users can be created and authenticated through validated schemas and service logic.
- Passwords are strongly hashed and never logged or returned.
- Access tokens have validated claims and configurable expiry.
- Reusable authorization dependencies enforce all three roles consistently.
- Disabled or invalid accounts and malformed, expired, or forged tokens are rejected safely.

**Tests required:** Password hashing tests; successful and failed authentication tests; token validation/expiry tests; role-permission matrix tests; schema validation and authorization integration tests.

## 4. Crime-data management

**Goal:** Provide normalized, validated ingestion and authorized management of crime incidents for downstream risk analysis.

**Modules involved:** `backend/app/api/crimes.py`; crime-incident model; crime schemas; crime service/repository components; import scripts where required; `data/raw/`, `data/processed/`, and `data/sample/` conventions.

**Dependencies:** Authentication and RBAC; database foundation; geospatial data types; an agreed crime category/severity representation.

**Acceptance criteria:**

- Authorized roles can create, read, update, and, where approved, deactivate crime records.
- Coordinates, timestamps, severity, categories, pagination, and filters are validated.
- Database access and preprocessing remain outside route handlers.
- Bulk ingestion is idempotent or detects duplicates and reports rejected rows clearly.
- Sample data is explicitly separated from operational data.

**Tests required:** CRUD permission tests; schema boundary tests; pagination/filter tests; spatial persistence tests; bulk import, duplicate, and malformed-row tests.

## 5. Geospatial/map services

**Goal:** Establish reusable geospatial calculations and an OSRM-compatible routing abstraction without coupling the system to one public server.

**Modules involved:** `backend/app/services/location_service.py`; spatial database helpers; routing client abstraction; shared API schemas; later-facing map service adapters in mobile and dashboard only as needed.

**Dependencies:** Crime-data management; PostGIS; configurable routing endpoint, timeout, and retry policy; OpenStreetMap-compatible coordinate conventions.

**Acceptance criteria:**

- Coordinate order, spatial reference, distance units, and validation are consistent.
- Radius and nearest-neighbor queries use PostGIS appropriately.
- Routing interface can use any compatible OSRM deployment through configuration.
- Network failures, timeouts, and unavailable routes produce meaningful typed errors.
- No operational location data is exposed merely because a map endpoint exists.

**Tests required:** Geodesic/spatial calculation tests; coordinate validation tests; PostGIS query integration tests; mocked routing success/error/timeout tests; authorization and privacy tests.

## 6. Risk-scoring engine

**Goal:** Implement an explainable, configurable weighted risk model using crime frequency, severity, time decay, and time-of-day contributions, normalized to a practical range.

**Modules involved:** `backend/app/optimization/risk_scoring.py`; `backend/app/services/risk_service.py`; risk-score model and schemas when persistence is required; configuration in `backend/app/core/`.

**Dependencies:** Crime-data management; geospatial services; NumPy/Pandas only where they improve correct batch computation; configured weights and decay lambda.

**Acceptance criteria:**

- Each contribution is explicit, typed, independently testable, and included in an explainable result.
- Recency uses configurable exponential time decay based on incident age.
- Risk weights and time buckets are validated configuration.
- Normalization is deterministic and handles empty and constant datasets.
- The implementation makes no predictive-ML claims and does not add scikit-learn.

**Tests required:** Unit tests for every contribution; time-decay reference-value tests; normalization edge cases; configuration validation tests; reproducibility and batch-performance tests.

## 7. Candidate PRP generation

**Goal:** Generate defensible candidate patrol positioning locations from risk and spatial data without equating candidates with selected deployments.

**Modules involved:** `backend/app/optimization/candidate_generator.py`; risk service; location service; candidate schemas or internal typed structures; optional persistence linked to optimization runs.

**Dependencies:** Risk-scoring engine; geospatial services; configured resolution, clustering/deduplication, boundary, and minimum-risk rules.

**Acceptance criteria:**

- Candidate generation is deterministic for identical inputs and configuration.
- Nearby duplicate candidates are consolidated by a documented spatial rule.
- Candidates retain explainability and traceability to source risk data.
- Invalid, out-of-area, or unsupported coordinates are rejected.
- Candidate generation does not expose or publish operational PRPs.

**Tests required:** Determinism tests; spatial deduplication tests; boundary and empty-input tests; traceability tests; representative dataset performance tests.

## 8. PRP optimization

**Goal:** Select at most the available number of PRPs to maximize total weighted risk covered within the configurable coverage radius.

**Modules involved:** `backend/app/optimization/coverage.py`; `backend/app/optimization/prp_optimizer.py`; `backend/app/api/prp.py`; PRP-location and optimization-run models/schemas as required; optimization service layer.

**Dependencies:** Candidate PRP generation; Google OR-Tools; geospatial distance/coverage matrix; available patrol count; configurable coverage radius defaulting to 3 km.

**Acceptance criteria:**

- Objective and constraints implement weighted maximum coverage rather than top-N ranking.
- Selected PRP count never exceeds eligible available patrol units.
- Coverage radius is supplied through validated configuration or request policy, not hard-coded throughout logic.
- Solver status, inputs, configuration, objective, and outputs are auditable through optimization runs.
- Empty inputs, zero patrols, infeasible cases, and solver limits return safe, meaningful results.
- Operational results are accessible only to authorized `ADMIN` and permitted `POLICE` users.

**Tests required:** Coverage-matrix unit tests; small brute-force optimality comparisons; overlap scenarios proving behavior differs from top-N; constraint and edge-case tests; solver timeout/status tests; API authorization/privacy tests.

## 9. Patrol allocation

**Goal:** Assign selected PRPs to eligible patrol units using clear operational constraints, without conflating strategic assignment with emergency dispatch.

**Modules involved:** `backend/app/optimization/assignment.py`; `backend/app/api/patrols.py`; patrol-unit and patrol-assignment models/schemas; patrol allocation service; location service.

**Dependencies:** PRP optimization; authentication/RBAC; patrol availability and capability data; routing/distance abstraction.

**Acceptance criteria:**

- Only eligible, available units are assigned.
- Each unit and active PRP obeys configured one-to-one or approved capacity constraints.
- Assignment state transitions and optimization-run provenance are auditable.
- Reallocation handles unavailable units without corrupting existing assignment history.
- Allocation service logic remains separate from route handlers and SOS dispatch.

**Tests required:** Eligibility and constraint tests; deterministic assignment tests; state-transition tests; unavailable-unit/reallocation tests; database transaction and API authorization tests.

## 10. Admin dashboard

**Goal:** Provide authorized administrators with operational management, map visualization, and optimization controls through one React + Vite dashboard.

**Modules involved:** `admin-dashboard/src/pages/`; `components/`; `services/`; `maps/`; authentication state/routing within the existing dashboard; relevant backend admin APIs in `backend/app/api/admin.py`.

**Dependencies:** Authentication/RBAC; crime management; PRP optimization; patrol allocation; React Leaflet/Leaflet with OpenStreetMap; stable backend contracts.

**Acceptance criteria:**

- Admin login and protected navigation enforce authorization on both UI and backend.
- Authorized users can manage crime data, inspect risks, run/inspect optimization, and view patrol assignments as approved.
- Map layers distinguish incidents, candidates, PRPs, and patrols clearly.
- Loading, empty, validation, and API error states are usable and accessible.
- Operational data is not cached or exposed to unauthorized sessions.

**Tests required:** Component and service tests; protected-route tests; map-layer tests; API contract tests; lint/type/build checks; end-to-end critical admin workflow test.

## 11. Police application

**Goal:** Implement the police role inside the single Flutter application for assignments, operational maps, availability, and later SOS response workflows.

**Modules involved:** `mobile/safezone_app/lib/police/`; shared models/widgets; mobile services; authentication and secure storage; police-facing backend patrol/PRP APIs.

**Dependencies:** Authentication/RBAC; patrol allocation; geospatial services; `flutter_map` with OpenStreetMap; agreed mobile API contracts.

**Acceptance criteria:**

- Police users enter only police-authorized screens within the single role-based app.
- Officers can update availability and view their own authorized assignments/PRPs.
- Operational maps and state changes handle offline, retry, and stale-data conditions safely.
- Citizen accounts cannot access police screens or operational endpoints.
- Sensitive tokens and operational data use appropriate device storage and lifecycle controls.

**Tests required:** Flutter unit/widget tests; role-navigation tests; API serialization/error tests; availability/assignment workflow tests; analyze/build checks; backend permission tests.

## 12. Citizen application

**Goal:** Implement citizen capabilities inside the same Flutter application while preventing exposure of operational deployment information.

**Modules involved:** `mobile/safezone_app/lib/citizen/`; shared UI/models; mobile services; citizen-facing authentication/profile APIs; emergency-contact model/API when required.

**Dependencies:** Authentication/RBAC; single Flutter application foundation; geospatial permission handling; citizen-safe backend contracts.

**Acceptance criteria:**

- Citizen registration/login and role-based navigation work in the shared application.
- Citizen screens do not receive exact PRPs, patrol routes, or precise deployment data.
- Location permission states and denial paths are clear and safe.
- Emergency contacts, if included in this stage, are privately scoped to their owner.
- UI handles accessibility, loading, empty, and network-error states.

**Tests required:** Flutter unit/widget tests; citizen role-navigation tests; privacy/response-schema tests; permission-denial tests; API serialization tests; analyze/build checks.

## 13. SOS dispatch

**Goal:** Implement the real-time emergency request lifecycle by assigning the nearest suitable available patrol without triggering PRP optimization.

**Modules involved:** `backend/app/api/sos.py`; `backend/app/services/dispatch_service.py`; SOS-request model/schemas; patrol service; location/routing service; citizen and police SOS UI/services.

**Dependencies:** Citizen and police applications; patrol availability/location data; authentication/RBAC; routing abstraction; transactional database foundation.

**Acceptance criteria:**

- A validated citizen SOS creates one auditable request with its location and timestamp.
- Dispatch selects the nearest suitable `AVAILABLE` patrol using distance/route policy and concurrency-safe reservation.
- State flow supports assignment, officer acceptance, `EN_ROUTE`, `ARRIVED`, and `RESOLVED`, with only approved cancellation/failure transitions.
- SOS creation never invokes full PRP optimization.
- Citizens receive status and permitted approximation/ETA information, never exact PRPs or operational deployment details.
- Duplicate submissions and simultaneous dispatch attempts are handled safely.

**Tests required:** Dispatch selection tests; no-available-patrol tests; lifecycle transition tests; concurrency/idempotency tests; privacy/RBAC tests; routing failure tests; end-to-end citizen-to-officer workflow test.

## 14. Live location and notifications

**Goal:** Add controlled live location/status updates and notification delivery for active operations through abstractions that remain testable and provider-independent.

**Modules involved:** location-update model/schemas; WebSocket endpoints only where justified; `backend/app/services/notification_service.py`; FCM adapter; mobile notification/location services; active SOS and patrol workflows.

**Dependencies:** SOS dispatch; patrol allocation; Firebase project/device registration configuration; authentication for REST/WebSocket; retention and update-frequency policy.

**Acceptance criteria:**

- Location updates are accepted only from authorized subjects, validated, rate-limited, and scoped to active needs.
- WebSocket connections authenticate and authorize subscriptions when used.
- Notification service exposes a provider-neutral interface with configurable FCM implementation.
- Failures use bounded retry/idempotency behavior without blocking core transactions.
- Retention and citizen-visible precision follow privacy policy.
- Update frequency avoids unnecessary polling, writes, and battery/network usage.

**Tests required:** Location validation/rate-limit tests; WebSocket authentication/subscription tests; mocked FCM tests; retry/idempotency tests; retention/privacy tests; active-SOS integration tests.

## 15. Analytics/evaluation

**Goal:** Measure explainable risk, coverage, assignment, and response performance without misrepresenting the system as predictive AI.

**Modules involved:** `backend/app/api/admin.py`; analytics services/schemas; optimization-run and risk-score history; `notebooks/` for clearly separated analysis; admin dashboard analytics pages/components.

**Dependencies:** Risk scoring; PRP optimization; patrol allocation; SOS lifecycle data; approved metric definitions; Pandas/NumPy where appropriate.

**Acceptance criteria:**

- Metrics include risk coverage, overlap/coverage efficiency, patrol utilization, dispatch distance/time, and SOS response milestones where data permits.
- Metrics define populations, time windows, units, missing-data rules, and limitations.
- Operational queries are bounded and indexed and do not recompute unchanged results unnecessarily.
- Analytics permissions and aggregation avoid exposing individual or operational data improperly.
- Notebooks consume separated sample/anonymized data and are not production service dependencies.

**Tests required:** Metric reference-dataset tests; time-window and missing-data tests; authorization/privacy tests; query-plan/performance checks; dashboard visualization and API contract tests.

## 16. Testing/security/performance hardening

**Goal:** Validate cross-system correctness and harden security, reliability, privacy, and latency before deployment preparation.

**Modules involved:** All backend, mobile, dashboard, database, optimization, and integration modules; test suites; CI configuration; security and performance scripts.

**Dependencies:** Completion of all functional stages; representative anonymized/sample datasets; defined service-level targets; supported test environments.

**Acceptance criteria:**

- Automated test pyramid covers critical unit, integration, contract, and end-to-end behavior.
- Authorization and privacy matrices cover every endpoint and live channel.
- Input validation, secret handling, dependency risks, logging redaction, and common web/mobile vulnerabilities are reviewed.
- Database queries, risk calculation, optimization, dispatch, dashboard, and mobile critical paths meet documented targets.
- Concurrency, retry, degradation, and recovery behavior are tested.
- No ignored failures, flaky critical tests, debug credentials, or duplicate implementations remain.

**Tests required:** Full backend suite with coverage; migration suite; Flutter tests/analyze/build; dashboard tests/lint/type/build; end-to-end flows; dependency/secret/security scans; load, concurrency, and solver performance tests.

## 17. Deployment preparation

**Goal:** Package the verified system for reproducible, configurable deployment using Docker and Docker Compose without embedding infrastructure credentials.

**Modules involved:** Backend `Dockerfile`; root `docker-compose.yml`; `.env.example`; deployment scripts/docs; PostgreSQL/PostGIS, backend, dashboard, and routing/notification configuration; health endpoints.

**Dependencies:** Hardened applications; selected deployment environments; database migration and backup policies; externally managed secrets; OSRM-compatible and FCM infrastructure decisions.

**Acceptance criteria:**

- Images build reproducibly with minimal production runtime contents and non-root execution where practical.
- Compose supports a documented local/integration environment with health checks and ordered readiness.
- Configuration and secrets are externalized, validated, and documented in `.env.example`.
- Database migrations run through an explicit safe procedure; backup/restore and rollback are documented.
- CORS, trusted hosts, TLS termination assumptions, logging, and observability are environment-aware.
- No public routing or notification provider is hard-wired into business logic.

**Tests required:** Clean Docker image builds; Compose startup/health smoke test; migration on fresh and existing database; configuration-failure tests; container security scan; deployed API/dashboard/mobile integration smoke test.

## 18. Final integration audit

**Goal:** Verify the delivered repository conforms to the frozen architecture and requirements and is ready for final-year project demonstration and evaluation.

**Modules involved:** Entire repository, documentation, migrations, configuration, applications, services, tests, sample data, and deployment artifacts.

**Dependencies:** All preceding stages complete; acceptance evidence; final supported toolchain and environment inventory.

**Acceptance criteria:**

- Required repository structure remains intact with one backend, one role-based Flutter app, and one React/Vite dashboard.
- All public APIs are documented and backward compatibility decisions are recorded.
- PRP optimization and SOS dispatch remain separate in code, data flows, and user experience.
- Citizen privacy rule is enforced in schemas, endpoints, live updates, logs, analytics, and UI.
- Configurable coverage radius, risk weights, routing, credentials, and infrastructure contain no scattered production constants.
- No duplicate, experimental, temporary, dead, or untracked production implementation remains.
- Architecture, setup, operation, demo, limitations, and recovery documentation match the delivered system.
- All required checks pass from a clean checkout.

**Tests required:** Full clean-environment CI run; repository architecture audit; API/RBAC/privacy matrix regression; representative risk/optimization/dispatch scenarios; clean deployment rehearsal; mobile and dashboard production builds; secrets and dependency scans; documented acceptance checklist sign-off.
