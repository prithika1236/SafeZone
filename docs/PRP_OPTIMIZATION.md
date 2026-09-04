# Dynamic PRP optimization

Stage 8 selects strategic patrol positioning points for a specific shift. A PRP is not a
police station and this workflow is not SOS dispatch. SOS requests must later use a separate,
real-time nearest-suitable-patrol process.

## Inputs and coverage

The optimizer receives deterministic candidate PRPs from Stage 7 and weighted demand points
from the explainable Stage 6 risk process. Candidate `j` covers demand `i` when their geodesic
distance is less than or equal to the configured coverage radius. This radius is supplied per
run and is persisted; it is never fixed at 3 km in the optimizer.

Straight-line geodesic coverage is used for the strategic maximum-coverage model. Road-route
distance is a separate concern and the routing abstraction is not silently substituted when a
routing provider is unavailable.

## Mathematical formulation

Let `x_j` be 1 when candidate `j` is selected, `y_i` be 1 when demand point `i` is covered,
`w_i` be its non-negative risk weight, `C_i` be the candidates that cover it, and `P` be the
available patrol count.

```text
maximize    sum_i(w_i * y_i)

subject to  sum_j(x_j) <= P
            y_i <= sum_{j in C_i}(x_j)              for every i
            sum_{j in C_i}(x_j) <= |C_i| * y_i      for every i with C_i non-empty
            y_i = 0                                  when C_i is empty
            x_j, y_i in {0, 1}
```

Because each demand has one `y_i`, overlapping PRPs never multiply its objective contribution.
OR-Tools CP-SAT requires integer objective coefficients, so configurable fixed-point scaling is
used. Every positive risk retains at least one scaled unit. A secondary deterministic penalty
prefers fewer PRPs and stable candidate-ID ordering only after maximum covered risk is preserved.

## Workflow and persistence

- `POST /prp/preview` solves without persistence.
- `POST /prp/generate` creates an `OptimizationRun` and stores selected `PRPLocation` records as
  `CANDIDATE`.
- `GET /prp/runs/{run_id}` returns the reproducible request, result and generated points.
- `POST /prp/runs/{run_id}/approve` changes generated candidates to `APPROVED`.
- `POST /prp/runs/{run_id}/activate` atomically retires previously active PRPs whose shift windows
  overlap this run and activates the approved points in that run.
- `GET /prp/active` lists active operational points.

All endpoints are ADMIN-only. There is no Citizen PRP endpoint, and exact locations must never
be copied into citizen-facing DTOs. The persisted metadata assigns each covered demand to one
selected PRP so per-PRP covered-risk totals remain auditable without double-counting.

## Result interpretation and limits

Results contain solver status, selected PRPs, unique covered demand IDs, covered and total
weighted risk, percentage coverage, uncovered points meeting the configured high-risk threshold,
and solver/configuration metadata. `NOT_RUN` is returned safely for zero patrols, no candidates,
or no demand. `FEASIBLE` means the configured time limit ended with a valid solution; only
`OPTIMAL` proves the mathematical optimum.

This stage assumes generated candidates are operationally suitable according to Stage 7 metadata.
It does not allocate officers, calculate road ETAs, respond to SOS requests, or publish PRPs to
citizens.
