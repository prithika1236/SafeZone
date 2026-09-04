# Patrol assignment

Stage 9 converts approved strategic PRPs into shift-bounded patrol assignments. It is a
deterministic allocation workflow, not predictive AI and not SOS dispatch.

## Assignment strategy

The allocator processes PRPs by descending calculated risk, with PRP ID as a stable tie-breaker.
For each PRP it chooses the nearest eligible patrol-unit/officer pair using the Stage 5 geodesic
distance calculation. Unit and officer identifiers provide stable tie-breakers. A resource with no
location remains eligible only after every located resource; its distance is returned as `null` and
is never silently assumed to be zero.

Only units and officers marked `AVAILABLE` enter a new automatic plan. Each pair can be used once
per plan. Existing open assignments are checked for overlapping half-open shift windows
`[shift_start, shift_end)`. PostgreSQL exclusion constraints independently prevent concurrent
requests from assigning the same unit or officer to overlapping shifts.

The initial data model has no permanent officer-to-unit membership. Automatic allocation therefore
pairs available units and officers deterministically by unit identifier and badge identifier before
matching those pairs to PRPs. A later operational roster may replace only that pairing input without
changing the allocation interface.

## Lifecycle

New records use:

```text
ASSIGNED -> ACKNOWLEDGED -> AT_PRP -> COMPLETED
```

An acknowledged officer may complete early when operationally necessary. ADMIN may cancel an open
assignment. Completion or cancellation releases its unit and officer when no other open assignment
uses them. `UNAVAILABLE` is retained as a supported lifecycle value, while automatic planning
reports unassigned PRPs without fabricating assignment records.

Legacy `PLANNED` and `ACTIVE` enum values remain readable for backward compatibility.

## API and privacy

ADMIN operations:

- `POST /patrols/assignments/automatic`
- `GET /patrols/assignments`
- `GET /patrols/assignments/{assignment_id}`
- `PATCH /patrols/assignments/{assignment_id}/override`
- `POST /patrols/assignments/{assignment_id}/cancel`

POLICE operations:

- `GET /patrols/assignments/current`
- `POST /patrols/assignments/{assignment_id}/acknowledge`
- `POST /patrols/assignments/{assignment_id}/arrive`
- `POST /patrols/assignments/{assignment_id}/complete`

Police lifecycle operations verify that the authenticated user owns the linked officer record.
Citizens have no assignment endpoints and receive no exact PRP or deployment data.

Road-route estimates are not fabricated when OSRM-compatible routing is unavailable. This MVP uses
explicit straight-line proximity for deterministic allocation; route-aware ranking can later be
added through the existing routing abstraction.

