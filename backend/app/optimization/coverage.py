"""Deterministic geodesic coverage relationships for PRP optimization."""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.optimization.candidate_generator import CandidatePRP
from app.schemas.location import Coordinate
from app.services.location_service import geodesic_distance_meters, validate_radius


class DemandPoint(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    demand_id: str = Field(min_length=1, max_length=160)
    location: Coordinate
    risk_weight: float = Field(ge=0, le=1)


class CoverageMatrix(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_ids: tuple[str, ...]
    demand_ids: tuple[str, ...]
    demands_by_candidate: tuple[tuple[int, ...], ...]
    candidates_by_demand: tuple[tuple[int, ...], ...]
    coverage_radius_meters: float


def build_coverage_matrix(
    candidates: Sequence[CandidatePRP],
    demand_points: Sequence[DemandPoint],
    coverage_radius_meters: float,
) -> CoverageMatrix:
    """Return exact within-radius relationships using one consistent meter convention."""
    radius = validate_radius(coverage_radius_meters)
    ordered_candidates = sorted(candidates, key=lambda item: item.candidate_id)
    ordered_demands = sorted(demand_points, key=lambda item: item.demand_id)
    if len({item.candidate_id for item in ordered_candidates}) != len(ordered_candidates):
        raise ValueError("candidate IDs must be unique")
    if len({item.demand_id for item in ordered_demands}) != len(ordered_demands):
        raise ValueError("demand IDs must be unique")
    if not all(math.isfinite(item.risk_weight) for item in ordered_demands):
        raise ValueError("demand risk weights must be finite")

    by_candidate: list[list[int]] = [[] for _ in ordered_candidates]
    by_demand: list[list[int]] = [[] for _ in ordered_demands]
    for candidate_index, candidate in enumerate(ordered_candidates):
        for demand_index, demand in enumerate(ordered_demands):
            if (
                geodesic_distance_meters(candidate.location, demand.location)
                <= radius
            ):
                by_candidate[candidate_index].append(demand_index)
                by_demand[demand_index].append(candidate_index)
    return CoverageMatrix(
        candidate_ids=tuple(item.candidate_id for item in ordered_candidates),
        demand_ids=tuple(item.demand_id for item in ordered_demands),
        demands_by_candidate=tuple(tuple(values) for values in by_candidate),
        candidates_by_demand=tuple(tuple(values) for values in by_demand),
        coverage_radius_meters=radius,
    )
