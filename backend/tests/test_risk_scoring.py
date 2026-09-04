"""Reference and edge-case tests for the explainable weighted risk model."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.optimization.risk_scoring import (
    RiskCandidate,
    RiskIncident,
    RiskModelConfig,
    ShiftWindow,
    calculate_candidate_risk,
    calculate_risk_batch,
    normalize_risk_results,
    recency_decay,
)
from app.schemas.location import Coordinate
from app.services.risk_service import persist_risk_result, risk_config_from_settings

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
DAY_SHIFT = ShiftWindow(
    start=datetime(2026, 9, 5, 8, tzinfo=UTC),
    end=datetime(2026, 9, 5, 16, tzinfo=UTC),
)
LOCATION = Coordinate(latitude=12.9716, longitude=77.5946)


def candidate(*incidents: RiskIncident, candidate_id: str = "candidate-a") -> RiskCandidate:
    return RiskCandidate(candidate_id=candidate_id, location=LOCATION, incidents=incidents)


def incident(*, days_old: float = 1, severity: int = 3, hour: int = 10) -> RiskIncident:
    occurred = (NOW - timedelta(days=days_old)).replace(hour=hour)
    return RiskIncident(severity=severity, occurred_at=occurred, crime_type="THEFT")


def test_recency_formula_reference_value_and_recent_incident_wins() -> None:
    assert recency_decay(10, 0.1) == pytest.approx(0.3678794412)
    config = RiskModelConfig(
        frequency_weight=0, severity_weight=0, recency_weight=1, time_weight=0
    )
    recent = calculate_candidate_risk(candidate(incident(days_old=1)), DAY_SHIFT, as_of=NOW, config=config)
    old = calculate_candidate_risk(candidate(incident(days_old=30)), DAY_SHIFT, as_of=NOW, config=config)
    assert recent.total_risk > old.total_risk


def test_configured_severe_incident_contributes_more() -> None:
    config = RiskModelConfig(
        frequency_weight=0, severity_weight=1, recency_weight=0, time_weight=0,
        severity_mapping={1: 0.05, 2: 0.2, 3: 0.5, 4: 0.8, 5: 1.0},
    )
    low = calculate_candidate_risk(candidate(incident(severity=1)), DAY_SHIFT, as_of=NOW, config=config)
    high = calculate_candidate_risk(candidate(incident(severity=5)), DAY_SHIFT, as_of=NOW, config=config)
    assert low.components.severity_raw == 0.05
    assert high.components.severity_raw == 1.0
    assert high.total_risk > low.total_risk


def test_selected_shift_time_changes_relevance() -> None:
    config = RiskModelConfig(
        frequency_weight=0, severity_weight=0, recency_weight=0, time_weight=1,
        time_relevance_floor=0.2,
    )
    historical = candidate(incident(hour=10))
    day = calculate_candidate_risk(historical, DAY_SHIFT, as_of=NOW, config=config)
    night_shift = ShiftWindow(
        start=datetime(2026, 9, 5, 20, tzinfo=UTC),
        end=datetime(2026, 9, 6, 4, tzinfo=UTC),
    )
    night = calculate_candidate_risk(historical, night_shift, as_of=NOW, config=config)
    assert day.components.time_raw == 1
    assert night.components.time_raw == 0.2
    assert day.total_risk > night.total_risk


def test_no_incidents_produces_explainable_zero() -> None:
    result = calculate_candidate_risk(candidate(), DAY_SHIFT, as_of=NOW, config=RiskModelConfig())
    assert result.total_risk == 0
    assert result.raw_total_risk == 0
    assert result.components.incident_count == 0
    assert result.components.model_dump(exclude={"incident_count"}) == {
        key: 0 for key in result.components.model_dump(exclude={"incident_count"})
    }


def test_batch_normalization_empty_range_and_constant_cases() -> None:
    config = RiskModelConfig(
        frequency_weight=1, severity_weight=0, recency_weight=0, time_weight=0
    )
    low = calculate_candidate_risk(candidate(incident(), candidate_id="low"), DAY_SHIFT, as_of=NOW, config=config)
    high = calculate_candidate_risk(
        candidate(incident(), incident(), incident(), candidate_id="high"),
        DAY_SHIFT, as_of=NOW, config=config,
    )
    normalized = normalize_risk_results([low, high])
    assert [item.total_risk for item in normalized] == pytest.approx([0, 1])
    assert normalize_risk_results([]) == []
    assert [item.total_risk for item in normalize_risk_results([low, low])] == [1, 1]
    zero = calculate_candidate_risk(candidate(), DAY_SHIFT, as_of=NOW, config=config)
    assert normalize_risk_results([zero])[0].total_risk == 0


@pytest.mark.parametrize(
    "values",
    [
        {"frequency_weight": 0, "severity_weight": 0, "recency_weight": 0, "time_weight": 0},
        {"recency_decay_lambda": 0},
        {"severity_mapping": {1: 0.2}},
        {"severity_mapping": {1: 0.2, 2: 0.4, 3: 0.3, 4: 0.8, 5: 1.0}},
        {"time_relevance_floor": 1.1},
    ],
)
def test_invalid_configuration_is_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RiskModelConfig(**values)


def test_identical_inputs_are_deterministic_and_components_sum_to_total() -> None:
    config = RiskModelConfig()
    value = candidate(incident(), incident(days_old=5, severity=5, hour=22))
    first = calculate_candidate_risk(value, DAY_SHIFT, as_of=NOW, config=config)
    second = calculate_candidate_risk(value, DAY_SHIFT, as_of=NOW, config=config)
    assert first == second
    components = first.components
    assert first.total_risk == pytest.approx(
        components.frequency_weighted + components.severity_weighted
        + components.recency_weighted + components.time_weighted
    )


def test_batch_calculation_handles_representative_input() -> None:
    inputs = [candidate(incident(days_old=index % 30), candidate_id=str(index)) for index in range(500)]
    results = calculate_risk_batch(inputs, DAY_SHIFT, as_of=NOW, config=RiskModelConfig())
    assert len(results) == 500
    assert all(0 <= result.total_risk <= 1 for result in results)


def test_settings_create_valid_explicit_configuration() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:password@localhost/safezone",
        JWT_SECRET_KEY="a-test-secret-with-more-than-32-characters",
    )
    config = risk_config_from_settings(settings)
    assert config.frequency_weight == settings.risk_frequency_weight
    assert config.severity_mapping[5] == 1.0


class PersistenceSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self.refreshes = 0
    def add(self, value: Any) -> None:
        self.added.append(value)
    async def commit(self) -> None:
        self.commits += 1
    async def refresh(self, _: Any) -> None:
        self.refreshes += 1


def test_persistence_occurs_only_through_explicit_service_call() -> None:
    config = RiskModelConfig()
    result = calculate_candidate_risk(candidate(incident()), DAY_SHIFT, as_of=NOW, config=config)
    session = PersistenceSession()
    record = asyncio.run(
        persist_risk_result(session, result, shift=DAY_SHIFT, config=config)
    )
    assert session.added == [record]
    assert session.commits == 1 and session.refreshes == 1
    assert float(record.score) == pytest.approx(result.total_risk)
    assert record.components["configuration"]["recency_decay_lambda"] == 0.05
