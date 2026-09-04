"""Pure, deterministic, explainable crime-risk scoring primitives."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.location import Coordinate

SECONDS_PER_DAY = 86_400.0


class RiskModelConfig(BaseModel):
    """Validated model policy; every scoring constant is explicit and reproducible."""

    model_config = ConfigDict(frozen=True)

    frequency_weight: float = Field(default=0.25, ge=0)
    severity_weight: float = Field(default=0.30, ge=0)
    recency_weight: float = Field(default=0.30, ge=0)
    time_weight: float = Field(default=0.15, ge=0)
    recency_decay_lambda: float = Field(default=0.05, gt=0)
    frequency_saturation_count: float = Field(default=5.0, gt=0)
    time_relevance_floor: float = Field(default=0.25, ge=0, le=1)
    severity_mapping: dict[int, float] = Field(
        default_factory=lambda: {1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0}
    )
    model_version: str = Field(default="weighted-risk-v1", min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        weights = (
            self.frequency_weight,
            self.severity_weight,
            self.recency_weight,
            self.time_weight,
        )
        if not all(math.isfinite(value) for value in weights):
            raise ValueError("risk weights must be finite")
        if sum(weights) <= 0:
            raise ValueError("at least one risk weight must be positive")
        if set(self.severity_mapping) != {1, 2, 3, 4, 5}:
            raise ValueError("severity_mapping must define levels 1 through 5")
        mapped = [self.severity_mapping[level] for level in range(1, 6)]
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in mapped):
            raise ValueError("severity mapping values must be finite and within 0..1")
        if mapped != sorted(mapped):
            raise ValueError("severity mapping must be non-decreasing")
        return self


class ShiftWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("shift timestamps must include timezone information")
        duration = (self.end - self.start).total_seconds()
        if duration <= 0 or duration > SECONDS_PER_DAY:
            raise ValueError("shift duration must be greater than zero and at most 24 hours")
        return self


class RiskIncident(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    severity: int = Field(ge=1, le=5)
    occurred_at: datetime
    crime_type: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_timestamp(self) -> Self:
        if self.occurred_at.tzinfo is None:
            raise ValueError("incident timestamp must include timezone information")
        return self


class RiskCandidate(BaseModel):
    """A location/area reference and the incidents associated with its analysis boundary."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1, max_length=160)
    location: Coordinate
    incidents: tuple[RiskIncident, ...] = ()


class RiskComponents(BaseModel):
    model_config = ConfigDict(frozen=True)

    incident_count: int
    frequency_raw: float
    severity_raw: float
    recency_raw: float
    time_raw: float
    frequency_weighted: float
    severity_weighted: float
    recency_weighted: float
    time_weighted: float


class RiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    location: Coordinate
    total_risk: float = Field(ge=0, le=1)
    raw_total_risk: float = Field(ge=0, le=1)
    components: RiskComponents
    model_version: str
    normalized_across_batch: bool = False


def recency_decay(age_in_days: float, decay_lambda: float) -> float:
    if not math.isfinite(age_in_days) or age_in_days < 0:
        raise ValueError("age_in_days must be finite and non-negative")
    if not math.isfinite(decay_lambda) or decay_lambda <= 0:
        raise ValueError("decay_lambda must be finite and positive")
    return math.exp(-decay_lambda * age_in_days)


def frequency_component(incident_count: int, saturation_count: float) -> float:
    if incident_count < 0:
        raise ValueError("incident_count cannot be negative")
    if not math.isfinite(saturation_count) or saturation_count <= 0:
        raise ValueError("saturation_count must be finite and positive")
    return 1 - math.exp(-incident_count / saturation_count)


def time_of_day_relevance(occurred_at: datetime, shift: ShiftWindow, floor: float) -> float:
    """Compare historical local time-of-day with the selected shift's time window."""
    if not 0 <= floor <= 1:
        raise ValueError("time relevance floor must be within 0..1")
    local_incident = occurred_at.astimezone(shift.start.tzinfo)
    incident_second = (
        local_incident.hour * 3600 + local_incident.minute * 60 + local_incident.second
    )
    shift_second = shift.start.hour * 3600 + shift.start.minute * 60 + shift.start.second
    duration = (shift.end - shift.start).total_seconds()
    circular_offset = (incident_second - shift_second) % SECONDS_PER_DAY
    return 1.0 if circular_offset <= duration else floor


def calculate_candidate_risk(
    candidate: RiskCandidate,
    shift: ShiftWindow,
    *,
    as_of: datetime,
    config: RiskModelConfig,
) -> RiskResult:
    if as_of.tzinfo is None:
        raise ValueError("as_of must include timezone information")
    if not candidate.incidents:
        components = RiskComponents(
            incident_count=0,
            frequency_raw=0,
            severity_raw=0,
            recency_raw=0,
            time_raw=0,
            frequency_weighted=0,
            severity_weighted=0,
            recency_weighted=0,
            time_weighted=0,
        )
        return RiskResult(
            candidate_id=candidate.candidate_id,
            location=candidate.location,
            total_risk=0,
            raw_total_risk=0,
            components=components,
            model_version=config.model_version,
        )

    severities: list[float] = []
    recencies: list[float] = []
    time_values: list[float] = []
    for incident in candidate.incidents:
        age_days = (as_of - incident.occurred_at).total_seconds() / SECONDS_PER_DAY
        if age_days < 0:
            raise ValueError("incident occurrence cannot be later than as_of")
        severities.append(config.severity_mapping[incident.severity])
        recencies.append(recency_decay(age_days, config.recency_decay_lambda))
        time_values.append(
            time_of_day_relevance(incident.occurred_at, shift, config.time_relevance_floor)
        )

    count = len(candidate.incidents)
    frequency_raw = frequency_component(count, config.frequency_saturation_count)
    severity_raw = math.fsum(severities) / count
    recency_raw = math.fsum(recencies) / count
    time_raw = math.fsum(time_values) / count
    weight_total = (
        config.frequency_weight
        + config.severity_weight
        + config.recency_weight
        + config.time_weight
    )
    weighted = (
        frequency_raw * config.frequency_weight,
        severity_raw * config.severity_weight,
        recency_raw * config.recency_weight,
        time_raw * config.time_weight,
    )
    total = min(1.0, max(0.0, math.fsum(weighted) / weight_total))
    components = RiskComponents(
        incident_count=count,
        frequency_raw=frequency_raw,
        severity_raw=severity_raw,
        recency_raw=recency_raw,
        time_raw=time_raw,
        frequency_weighted=weighted[0] / weight_total,
        severity_weighted=weighted[1] / weight_total,
        recency_weighted=weighted[2] / weight_total,
        time_weighted=weighted[3] / weight_total,
    )
    return RiskResult(
        candidate_id=candidate.candidate_id,
        location=candidate.location,
        total_risk=total,
        raw_total_risk=total,
        components=components,
        model_version=config.model_version,
    )


def normalize_risk_results(results: list[RiskResult]) -> list[RiskResult]:
    """Min-max normalize a batch; equal positive scores remain equally maximal."""
    if not results:
        return []
    values = [result.raw_total_risk for result in results]
    minimum, maximum = min(values), max(values)
    if math.isclose(minimum, maximum):
        normalized = [0.0 if math.isclose(maximum, 0.0) else 1.0] * len(results)
    else:
        normalized = [(value - minimum) / (maximum - minimum) for value in values]
    return [
        result.model_copy(
            update={"total_risk": score, "normalized_across_batch": True}
        )
        for result, score in zip(results, normalized, strict=True)
    ]


def calculate_risk_batch(
    candidates: list[RiskCandidate],
    shift: ShiftWindow,
    *,
    as_of: datetime,
    config: RiskModelConfig,
    normalize: bool = True,
) -> list[RiskResult]:
    calculated = [
        calculate_candidate_risk(candidate, shift, as_of=as_of, config=config)
        for candidate in candidates
    ]
    return normalize_risk_results(calculated) if normalize else calculated
