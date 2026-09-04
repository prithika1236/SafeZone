# Explainable weighted risk model

Stage 6 implements deterministic scoring, not predictive machine learning. A candidate may represent a point or an area's chosen reference point. Its incident set must be selected using an explicit spatial boundary and evaluation timestamp.

## Components

For `n` incidents:

```text
frequency = 1 - exp(-n / frequency_saturation_count)
severity  = mean(configured_severity_value[incident.severity])
recency   = mean(exp(-lambda * age_in_days))
time      = mean(1 when incident local time is inside the shift time window,
                 configured_time_floor otherwise)
```

The raw composite is a weighted mean:

```text
raw_total = (
    frequency_weight * frequency
  + severity_weight  * severity
  + recency_weight   * recency
  + time_weight      * time
) / sum(weights)
```

Every component and its weighted contribution remains in the result. Each component is bounded to 0–1, so `raw_total` is already a stable 0–1 absolute score.

Optional batch min-max normalization supports relative candidate comparison. Empty batches stay empty; all-zero batches stay zero; equal positive scores all normalize to one because they are tied for the batch maximum. `raw_total_risk` is retained after normalization.

## Severity strategy

Incidents carry an explicitly validated operational severity level from 1 through 5. Configuration maps those levels to monotonic 0–1 contributions. Default mapping is 1→0.2, 2→0.4, 3→0.6, 4→0.8, and 5→1.0.

Crime category names do not silently determine severity. Categories have different legal and operational meaning across jurisdictions. If SafeZone later needs category-based policy, it must be explicitly configured, documented, versioned, and tested rather than embedded as universal constants.

## Time and recency

Age is measured from the explicit timezone-aware `as_of` instant. Future incidents are rejected. Time-of-day relevance converts historical occurrences into the selected shift's timezone and supports shifts crossing midnight. Shifts must be longer than zero and no longer than 24 hours.

## Persistence

Pure functions never write to the database. `risk_service.py` loads eligible `REPORTED` and `VERIFIED` incidents and persists only when explicitly requested. A stored `RiskScore` includes the candidate reference, raw components, shift, complete configuration snapshot, model version, and optional optimization-run relationship.

## Configuration

```env
RISK_FREQUENCY_WEIGHT=0.25
RISK_SEVERITY_WEIGHT=0.30
RISK_RECENCY_WEIGHT=0.30
RISK_TIME_WEIGHT=0.15
RISK_RECENCY_DECAY_LAMBDA=0.05
RISK_FREQUENCY_SATURATION_COUNT=5
RISK_TIME_RELEVANCE_FLOOR=0.25
RISK_SEVERITY_MAPPING={"1":0.2,"2":0.4,"3":0.6,"4":0.8,"5":1.0}
RISK_MODEL_VERSION=weighted-risk-v1
```
