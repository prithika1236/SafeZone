"""Determinism, consolidation, suitability, and traceability tests for PRP candidates."""

import math

import pytest
from pydantic import ValidationError

from app.optimization.candidate_generator import (
    CandidateGenerationConfig,
    RiskAreaObservation,
    SafeCandidateNode,
    generate_candidates,
    risk_areas_from_results,
)
from app.optimization.risk_scoring import RiskComponents, RiskResult
from app.schemas.location import BoundingBox, Coordinate


def area(
    area_id: str,
    latitude: float,
    longitude: float,
    risk: float = 0.5,
    evidence: int = 1,
) -> RiskAreaObservation:
    return RiskAreaObservation(
        area_id=area_id,
        location=Coordinate(latitude=latitude, longitude=longitude),
        local_risk=risk,
        evidence_count=evidence,
        metadata={"source": "risk-grid"},
    )


def test_generation_is_deterministic_regardless_of_input_order() -> None:
    inputs = [area("b", 12.9719, 77.5946, 0.7), area("a", 12.9716, 77.5946, 0.5)]
    config = CandidateGenerationConfig(cluster_radius_meters=100)
    forward = generate_candidates(inputs, config=config)
    reverse = generate_candidates(list(reversed(inputs)), config=config)
    assert forward == reverse


def test_nearby_risk_areas_become_one_weighted_centroid_not_raw_crime_points() -> None:
    first = area("a", 12.9716, 77.5946, 0.2, evidence=1)
    second = area("b", 12.9720, 77.5946, 0.8, evidence=3)
    result = generate_candidates(
        [first, second], config=CandidateGenerationConfig(cluster_radius_meters=100)
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert first.location.latitude < candidate.location.latitude < second.location.latitude
    assert candidate.local_risk == pytest.approx((0.2 + 0.8 * 3) / 4)
    assert candidate.metadata.source_area_ids == ("a", "b")
    assert candidate.metadata.evidence_count == 4
    assert candidate.metadata.generation_method == "risk_area_centroid"
    assert candidate.metadata.operationally_verified is False


def test_centroid_snaps_to_nearest_predefined_safe_node() -> None:
    node = SafeCandidateNode(
        node_id="road-node-1",
        location=Coordinate(latitude=12.9720, longitude=77.5950),
        metadata={"kind": "approved_layby"},
    )
    result = generate_candidates(
        [area("a", 12.9716, 77.5946)],
        config=CandidateGenerationConfig(safe_node_snap_radius_meters=200),
        safe_nodes=[node],
    )
    candidate = result.candidates[0]
    assert candidate.location == node.location
    assert candidate.metadata.safe_node_id == "road-node-1"
    assert candidate.metadata.operationally_verified is True
    assert candidate.metadata.snap_distance_meters > 0


def test_supplied_safe_nodes_cause_unsuitable_clusters_to_be_excluded() -> None:
    far_node = SafeCandidateNode(
        node_id="far", location=Coordinate(latitude=13.5, longitude=78.5)
    )
    result = generate_candidates(
        [area("a", 12.9716, 77.5946)],
        config=CandidateGenerationConfig(safe_node_snap_radius_meters=100),
        safe_nodes=[far_node],
    )
    assert result.candidates == ()
    assert result.exclusions[0].reason == "no_safe_node_within_snap_radius"


def test_candidates_snapped_to_same_node_are_deduplicated() -> None:
    node = SafeCandidateNode(
        node_id="shared", location=Coordinate(latitude=12.9720, longitude=77.5946)
    )
    result = generate_candidates(
        [area("a", 12.9716, 77.5946, 0.8), area("b", 12.9724, 77.5946, 0.6)],
        config=CandidateGenerationConfig(
            cluster_radius_meters=10,
            deduplication_radius_meters=10,
            safe_node_snap_radius_meters=100,
        ),
        safe_nodes=[node],
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].metadata.source_area_ids == ("a", "b")
    assert len(result.candidates[0].metadata.absorbed_candidate_ids) == 1


def test_threshold_cluster_size_and_bounds_exclusions_are_explicit() -> None:
    bounds = BoundingBox(south=12, west=77, north=13, east=78)
    result = generate_candidates(
        [area("low", 12.5, 77.5, 0.01), area("outside", 14, 77.5, 0.8),
         area("single", 12.6, 77.6, 0.8)],
        config=CandidateGenerationConfig(minimum_local_risk=0.1, minimum_source_areas=2),
        operational_bounds=bounds,
    )
    assert result.candidates == ()
    reasons = {item.source_id: item.reason for item in result.exclusions}
    assert reasons == {
        "low": "below_minimum_risk",
        "outside": "outside_operational_bounds",
        "single": "insufficient_cluster_sources",
    }


def test_empty_input_is_safe() -> None:
    assert generate_candidates([], config=CandidateGenerationConfig()).candidates == ()


def test_candidate_ids_are_stable_and_configuration_versioned() -> None:
    initial = generate_candidates([area("a", 12.9, 77.5)], config=CandidateGenerationConfig())
    repeated = generate_candidates([area("a", 12.9, 77.5)], config=CandidateGenerationConfig())
    changed = generate_candidates(
        [area("a", 12.9, 77.5)],
        config=CandidateGenerationConfig(generator_version="risk-area-centroid-v2"),
    )
    assert initial.candidates[0].candidate_id == repeated.candidates[0].candidate_id
    assert initial.candidates[0].candidate_id != changed.candidates[0].candidate_id


@pytest.mark.parametrize(
    "values",
    [
        {"cluster_radius_meters": 0},
        {"deduplication_radius_meters": math.inf},
        {"minimum_local_risk": -0.1},
        {"minimum_source_areas": 0},
        {"maximum_candidates": 0},
    ],
)
def test_invalid_configuration_is_rejected(values) -> None:
    with pytest.raises(ValidationError):
        CandidateGenerationConfig(**values)


def test_duplicate_source_and_node_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError, match="risk area IDs"):
        generate_candidates(
            [area("same", 12.9, 77.5), area("same", 13.0, 77.6)],
            config=CandidateGenerationConfig(),
        )
    node = SafeCandidateNode(node_id="same", location=Coordinate(latitude=12.9, longitude=77.5))
    with pytest.raises(ValueError, match="node IDs"):
        generate_candidates(
            [area("a", 12.9, 77.5)], config=CandidateGenerationConfig(),
            safe_nodes=[node, node],
        )


def test_representative_dataset_is_bounded_and_sorted_deterministically() -> None:
    inputs = [
        area(str(index), 12.0 + index * 0.001, 77.0, risk=(index % 10 + 1) / 10)
        for index in range(200)
    ]
    result = generate_candidates(
        inputs,
        config=CandidateGenerationConfig(cluster_radius_meters=20, maximum_candidates=25),
    )
    assert len(result.candidates) == 25
    assert sum(item.reason == "maximum_candidate_limit" for item in result.exclusions) == 175
    ranking = [(candidate.local_risk, candidate.candidate_id) for candidate in result.candidates]
    assert ranking == sorted(ranking, key=lambda item: (-item[0], item[1]))


def test_stage_six_results_have_a_lossless_candidate_input_adapter() -> None:
    components = RiskComponents(
        incident_count=3, frequency_raw=0.4, severity_raw=0.6, recency_raw=0.8,
        time_raw=1.0, frequency_weighted=0.1, severity_weighted=0.2,
        recency_weighted=0.3, time_weighted=0.15,
    )
    result = RiskResult(
        candidate_id="risk-area-1", location=Coordinate(latitude=12.9, longitude=77.5),
        total_risk=0.75, raw_total_risk=0.72, components=components,
        model_version="weighted-risk-v1", normalized_across_batch=True,
    )
    adapted = risk_areas_from_results([result])[0]
    assert adapted.area_id == result.candidate_id
    assert adapted.location == result.location
    assert adapted.local_risk == result.total_risk
    assert adapted.evidence_count == 3
    assert adapted.metadata["raw_total_risk"] == 0.72
