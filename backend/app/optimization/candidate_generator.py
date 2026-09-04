"""Deterministic generation of possible—not selected—patrol response points."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.optimization.risk_scoring import RiskResult
from app.schemas.location import BoundingBox, Coordinate
from app.services.location_service import geodesic_distance_meters

MetadataValue = str | int | float | bool | None


class CandidateGenerationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    cluster_radius_meters: float = Field(default=500.0, gt=0)
    deduplication_radius_meters: float = Field(default=50.0, gt=0)
    safe_node_snap_radius_meters: float = Field(default=750.0, gt=0)
    minimum_local_risk: float = Field(default=0.05, ge=0, le=1)
    minimum_source_areas: int = Field(default=1, ge=1)
    maximum_candidates: int = Field(default=500, ge=1, le=10_000)
    require_safe_node_when_nodes_supplied: bool = True
    generator_version: str = Field(default="risk-area-centroid-v1", min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_finite_values(self) -> Self:
        values = (
            self.cluster_radius_meters,
            self.deduplication_radius_meters,
            self.safe_node_snap_radius_meters,
            self.minimum_local_risk,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("candidate generation numeric settings must be finite")
        return self


class RiskAreaObservation(BaseModel):
    """An already aggregated/scored area input; never a raw crime stopping point."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    area_id: str = Field(min_length=1, max_length=160)
    location: Coordinate
    local_risk: float = Field(ge=0, le=1)
    evidence_count: int = Field(default=1, ge=1)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


class SafeCandidateNode(BaseModel):
    """A predefined operationally suitable node supplied by a future road/provider adapter."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    node_id: str = Field(min_length=1, max_length=160)
    location: Coordinate
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


class SafeCandidateNodeProvider(Protocol):
    """Extension point for later road-network or approved-node sources."""

    def load_nodes(self, bounds: BoundingBox | None = None) -> Sequence[SafeCandidateNode]: ...


class CandidateMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_method: Literal["risk_area_centroid", "safe_node_snap"]
    generator_version: str
    source_area_ids: tuple[str, ...]
    source_metadata: dict[str, dict[str, MetadataValue]]
    evidence_count: int
    calculated_centroid: Coordinate
    operationally_verified: bool
    safe_node_id: str | None = None
    safe_node_metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    snap_distance_meters: float | None = None
    absorbed_candidate_ids: tuple[str, ...] = ()


class CandidatePRP(BaseModel):
    """Optimizer input only; this is not an approved or active PRP."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    location: Coordinate
    local_risk: float = Field(ge=0, le=1)
    metadata: CandidateMetadata


class CandidateExclusion(BaseModel):
    source_id: str
    reason: Literal[
        "below_minimum_risk",
        "outside_operational_bounds",
        "insufficient_cluster_sources",
        "no_safe_node_within_snap_radius",
        "maximum_candidate_limit",
    ]


class CandidateGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[CandidatePRP, ...]
    exclusions: tuple[CandidateExclusion, ...]


def risk_areas_from_results(results: Sequence[RiskResult]) -> list[RiskAreaObservation]:
    """Adapt current Stage 6 results without treating their source crimes as stop points."""
    return [
        RiskAreaObservation(
            area_id=result.candidate_id,
            location=result.location,
            local_risk=result.total_risk,
            evidence_count=max(1, result.components.incident_count),
            metadata={
                "risk_model_version": result.model_version,
                "raw_total_risk": result.raw_total_risk,
                "normalized_across_batch": result.normalized_across_batch,
            },
        )
        for result in results
    ]


def _inside_bounds(location: Coordinate, bounds: BoundingBox) -> bool:
    return (
        bounds.south <= location.latitude <= bounds.north
        and bounds.west <= location.longitude <= bounds.east
    )


def _cluster_observations(
    observations: list[RiskAreaObservation], radius_meters: float
) -> list[list[RiskAreaObservation]]:
    """Build deterministic single-link spatial components."""
    parent = list(range(len(observations)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for left in range(len(observations)):
        for right in range(left + 1, len(observations)):
            if (
                geodesic_distance_meters(
                    observations[left].location, observations[right].location
                )
                <= radius_meters
            ):
                union(left, right)

    groups: dict[int, list[RiskAreaObservation]] = {}
    for index, observation in enumerate(observations):
        groups.setdefault(find(index), []).append(observation)
    return [groups[key] for key in sorted(groups)]


def _weighted_centroid(observations: Sequence[RiskAreaObservation]) -> Coordinate:
    """Calculate a risk/evidence-weighted spherical centroid."""
    x = y = z = 0.0
    total_weight = 0.0
    for observation in observations:
        weight = max(observation.local_risk, 1e-12) * observation.evidence_count
        latitude = math.radians(observation.location.latitude)
        longitude = math.radians(observation.location.longitude)
        x += weight * math.cos(latitude) * math.cos(longitude)
        y += weight * math.cos(latitude) * math.sin(longitude)
        z += weight * math.sin(latitude)
        total_weight += weight
    x, y, z = x / total_weight, y / total_weight, z / total_weight
    longitude = math.degrees(math.atan2(y, x))
    latitude = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
    return Coordinate(latitude=latitude, longitude=longitude)


def _aggregate_risk(observations: Sequence[RiskAreaObservation]) -> float:
    evidence = sum(observation.evidence_count for observation in observations)
    return math.fsum(
        observation.local_risk * observation.evidence_count for observation in observations
    ) / evidence


def _candidate_id(
    source_ids: Sequence[str], location: Coordinate, safe_node_id: str | None, version: str
) -> str:
    identity = "|".join(
        (version, *sorted(source_ids), f"{location.latitude:.8f}", f"{location.longitude:.8f}", safe_node_id or "")
    )
    return f"candidate-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def _nearest_safe_node(
    centroid: Coordinate,
    nodes: Sequence[SafeCandidateNode],
    maximum_distance: float,
) -> tuple[SafeCandidateNode, float] | None:
    ranked = sorted(
        ((geodesic_distance_meters(centroid, node.location), node) for node in nodes),
        key=lambda item: (item[0], item[1].node_id),
    )
    if not ranked or ranked[0][0] > maximum_distance:
        return None
    return ranked[0][1], ranked[0][0]


def _deduplicate(
    candidates: list[CandidatePRP], radius_meters: float
) -> list[CandidatePRP]:
    kept: list[CandidatePRP] = []
    for candidate in sorted(candidates, key=lambda item: (-item.local_risk, item.candidate_id)):
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(kept)
                if geodesic_distance_meters(candidate.location, existing.location) <= radius_meters
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(candidate)
            continue
        existing = kept[duplicate_index]
        source_ids = tuple(
            sorted(set(existing.metadata.source_area_ids) | set(candidate.metadata.source_area_ids))
        )
        source_metadata = dict(existing.metadata.source_metadata)
        source_metadata.update(candidate.metadata.source_metadata)
        absorbed = tuple(
            sorted(
                set(existing.metadata.absorbed_candidate_ids)
                | set(candidate.metadata.absorbed_candidate_ids)
                | {candidate.candidate_id}
            )
        )
        kept[duplicate_index] = existing.model_copy(
            update={
                "metadata": existing.metadata.model_copy(
                    update={
                        "source_area_ids": source_ids,
                        "source_metadata": source_metadata,
                        "evidence_count": (
                            existing.metadata.evidence_count + candidate.metadata.evidence_count
                        ),
                        "absorbed_candidate_ids": absorbed,
                    }
                )
            }
        )
    return kept


def generate_candidates(
    risk_areas: Sequence[RiskAreaObservation],
    *,
    config: CandidateGenerationConfig,
    safe_nodes: Sequence[SafeCandidateNode] = (),
    operational_bounds: BoundingBox | None = None,
) -> CandidateGenerationResult:
    """Generate deterministic candidate inputs without selecting final PRPs."""
    ordered = sorted(risk_areas, key=lambda item: item.area_id)
    if len({item.area_id for item in ordered}) != len(ordered):
        raise ValueError("risk area IDs must be unique")
    ordered_nodes = sorted(safe_nodes, key=lambda item: item.node_id)
    nodes_were_supplied = bool(ordered_nodes)
    if len({item.node_id for item in ordered_nodes}) != len(ordered_nodes):
        raise ValueError("safe candidate node IDs must be unique")
    if operational_bounds:
        ordered_nodes = [
            node for node in ordered_nodes if _inside_bounds(node.location, operational_bounds)
        ]

    eligible: list[RiskAreaObservation] = []
    exclusions: list[CandidateExclusion] = []
    for area in ordered:
        if area.local_risk < config.minimum_local_risk:
            exclusions.append(
                CandidateExclusion(source_id=area.area_id, reason="below_minimum_risk")
            )
        elif operational_bounds and not _inside_bounds(area.location, operational_bounds):
            exclusions.append(
                CandidateExclusion(source_id=area.area_id, reason="outside_operational_bounds")
            )
        else:
            eligible.append(area)

    candidates: list[CandidatePRP] = []
    for cluster in _cluster_observations(eligible, config.cluster_radius_meters):
        source_ids = tuple(sorted(area.area_id for area in cluster))
        if len(cluster) < config.minimum_source_areas:
            exclusions.extend(
                CandidateExclusion(source_id=area_id, reason="insufficient_cluster_sources")
                for area_id in source_ids
            )
            continue
        centroid = _weighted_centroid(cluster)
        chosen_location = centroid
        safe_node: SafeCandidateNode | None = None
        snap_distance: float | None = None
        if nodes_were_supplied:
            match = _nearest_safe_node(
                centroid, ordered_nodes, config.safe_node_snap_radius_meters
            )
            if match:
                safe_node, snap_distance = match
                chosen_location = safe_node.location
            elif config.require_safe_node_when_nodes_supplied:
                exclusions.extend(
                    CandidateExclusion(
                        source_id=area_id, reason="no_safe_node_within_snap_radius"
                    )
                    for area_id in source_ids
                )
                continue

        method = "safe_node_snap" if safe_node else "risk_area_centroid"
        identifier = _candidate_id(
            source_ids,
            chosen_location,
            safe_node.node_id if safe_node else None,
            config.generator_version,
        )
        candidates.append(
            CandidatePRP(
                candidate_id=identifier,
                location=chosen_location,
                local_risk=_aggregate_risk(cluster),
                metadata=CandidateMetadata(
                    generation_method=method,
                    generator_version=config.generator_version,
                    source_area_ids=source_ids,
                    source_metadata={area.area_id: area.metadata for area in cluster},
                    evidence_count=sum(area.evidence_count for area in cluster),
                    calculated_centroid=centroid,
                    operationally_verified=safe_node is not None,
                    safe_node_id=safe_node.node_id if safe_node else None,
                    safe_node_metadata=safe_node.metadata if safe_node else {},
                    snap_distance_meters=snap_distance,
                ),
            )
        )

    deduplicated = _deduplicate(candidates, config.deduplication_radius_meters)
    ranked = sorted(deduplicated, key=lambda item: (-item.local_risk, item.candidate_id))
    for omitted in ranked[config.maximum_candidates :]:
        exclusions.extend(
            CandidateExclusion(source_id=source_id, reason="maximum_candidate_limit")
            for source_id in omitted.metadata.source_area_ids
        )
    return CandidateGenerationResult(
        candidates=tuple(ranked[: config.maximum_candidates]),
        exclusions=tuple(sorted(exclusions, key=lambda item: (item.source_id, item.reason))),
    )
