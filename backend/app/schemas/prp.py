"""ADMIN-only contracts for strategic PRP optimization workflows."""

from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import OptimizationRunStatus, PRPStatus
from app.optimization.candidate_generator import CandidatePRP
from app.optimization.coverage import DemandPoint
from app.optimization.prp_optimizer import PRPOptimizationResult, PRPOptimizerConfig
from app.optimization.risk_scoring import ShiftWindow
from app.schemas.location import Coordinate


class PRPOptimizationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: list[CandidatePRP] = Field(max_length=10_000)
    demand_points: list[DemandPoint] = Field(max_length=100_000)
    available_patrol_count: int = Field(ge=0)
    coverage_radius_meters: float = Field(gt=0)
    shift: ShiftWindow
    high_risk_threshold: float = Field(default=0.7, ge=0)
    objective_scale: int = Field(default=1_000_000, ge=1, le=1_000_000_000)
    maximum_solve_seconds: float = Field(default=10.0, gt=0, le=300)
    random_seed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_unique_identifiers(self) -> Self:
        candidate_ids = [item.candidate_id for item in self.candidates]
        demand_ids = [item.demand_id for item in self.demand_points]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        if len(demand_ids) != len(set(demand_ids)):
            raise ValueError("demand IDs must be unique")
        return self

    def optimizer_config(self) -> PRPOptimizerConfig:
        return PRPOptimizerConfig(
            coverage_radius_meters=self.coverage_radius_meters,
            high_risk_threshold=self.high_risk_threshold,
            objective_scale=self.objective_scale,
            maximum_solve_seconds=self.maximum_solve_seconds,
            random_seed=self.random_seed,
        )


class StoredPRPLocation(BaseModel):
    id: UUID
    optimization_run_id: UUID
    candidate_id: str
    location: Coordinate
    risk_score: float
    covered_risk: float
    coverage_radius_meters: float
    shift_start: datetime
    shift_end: datetime
    generated_at: datetime
    status: PRPStatus
    coverage_metadata: dict[str, Any]


class OptimizationRunDetail(BaseModel):
    id: UUID
    run_at: datetime
    available_patrol_count: int
    coverage_radius_meters: float
    status: OptimizationRunStatus
    failure_reason: str | None
    result: PRPOptimizationResult | None
    prp_locations: tuple[StoredPRPLocation, ...]

