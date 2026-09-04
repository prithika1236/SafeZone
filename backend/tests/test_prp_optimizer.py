"""Synthetic proofs for weighted maximum-coverage PRP selection."""

from datetime import UTC, datetime, timedelta

import pytest

from app.optimization.candidate_generator import CandidateMetadata, CandidatePRP
from app.optimization.coverage import DemandPoint, build_coverage_matrix
from app.optimization.prp_optimizer import PRPOptimizerConfig, SolverStatus, optimize_prps
from app.optimization.risk_scoring import ShiftWindow
from app.schemas.location import Coordinate


SHIFT = ShiftWindow(
    start=datetime(2026, 9, 4, 8, tzinfo=UTC),
    end=datetime(2026, 9, 4, 16, tzinfo=UTC),
)


def candidate(identifier: str, latitude: float, longitude: float, risk: float = 0.5) -> CandidatePRP:
    point = Coordinate(latitude=latitude, longitude=longitude)
    return CandidatePRP(
        candidate_id=identifier,
        location=point,
        local_risk=risk,
        metadata=CandidateMetadata(
            generation_method="risk_area_centroid",
            generator_version="test-v1",
            source_area_ids=(identifier,),
            source_metadata={},
            evidence_count=1,
            calculated_centroid=point,
            operationally_verified=False,
        ),
    )


def demand(identifier: str, latitude: float, longitude: float, risk: float) -> DemandPoint:
    return DemandPoint(
        demand_id=identifier,
        location=Coordinate(latitude=latitude, longitude=longitude),
        risk_weight=risk,
    )


def run(candidates, demands, patrols=1, radius=250):
    return optimize_prps(
        candidates,
        demands,
        available_patrol_count=patrols,
        shift=SHIFT,
        config=PRPOptimizerConfig(coverage_radius_meters=radius),
    )


def test_optimizer_respects_available_patrol_limit() -> None:
    result = run(
        [candidate("a", 0, 0), candidate("b", 0, 0.02), candidate("c", 0, 0.04)],
        [demand("one", 0, 0, 1), demand("two", 0, 0.02, 1), demand("three", 0, 0.04, 1)],
        patrols=2,
    )
    assert len(result.selected_prps) == 2
    assert result.metadata.selected_count <= 2


def test_overlapping_coverage_counts_demand_once_and_chooses_complementary_point() -> None:
    result = run(
        [candidate("a", 0, 0), candidate("b", 0, 0.0002), candidate("c", 0, 0.02)],
        [demand("shared", 0, 0.0001, 1), demand("separate", 0, 0.02, 0.4)],
        patrols=2,
        radius=100,
    )
    assert {item.candidate_id for item in result.selected_prps} == {"a", "c"}
    assert result.covered_weighted_risk == 1.4
    assert result.covered_demand_ids == ("separate", "shared")


def test_high_risk_demand_is_preferred_over_candidate_local_risk() -> None:
    result = run(
        [candidate("high-local", 0, 0, 1), candidate("high-coverage", 0, 0.02, 0.1)],
        [demand("low", 0, 0, 0.1), demand("high", 0, 0.02, 0.9)],
    )
    assert [item.candidate_id for item in result.selected_prps] == ["high-coverage"]
    assert result.covered_weighted_risk == 0.9


def test_coverage_radius_changes_result() -> None:
    candidates = [candidate("a", 0, 0)]
    demands = [demand("nearby", 0, 0.005, 0.5)]
    assert run(candidates, demands, radius=500).covered_weighted_risk == 0
    assert run(candidates, demands, radius=600).covered_weighted_risk == 0.5


def test_zero_patrols_is_safe_and_reports_uncovered_high_risk() -> None:
    result = run([candidate("a", 0, 0)], [demand("high", 0, 0, 0.9)], patrols=0)
    assert result.solver_status == SolverStatus.NOT_RUN
    assert result.selected_prps == ()
    assert [item.demand_id for item in result.uncovered_high_risk_points] == ["high"]


def test_no_candidates_is_safe() -> None:
    result = run([], [demand("high", 0, 0, 0.9)])
    assert result.solver_status == SolverStatus.NOT_RUN
    assert result.coverage_percentage == 0


def test_results_are_reproducible_for_identical_inputs() -> None:
    candidates = [candidate("b", 0, 0), candidate("a", 0, 0)]
    demands = [demand("only", 0, 0, 1)]
    first = run(candidates, demands)
    second = run(list(reversed(candidates)), demands)
    assert [item.candidate_id for item in first.selected_prps] == ["a"]
    assert first.selected_prps == second.selected_prps
    assert first.covered_demand_ids == second.covered_demand_ids
    assert first.covered_weighted_risk == second.covered_weighted_risk


def test_coverage_matrix_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="candidate IDs must be unique"):
        build_coverage_matrix(
            [candidate("a", 0, 0), candidate("a", 1, 1)],
            [],
            100,
        )


def test_invalid_optimizer_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        PRPOptimizerConfig(coverage_radius_meters=float("inf"))
