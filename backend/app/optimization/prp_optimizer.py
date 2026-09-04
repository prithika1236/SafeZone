"""Google OR-Tools weighted maximum-coverage optimizer for strategic PRPs."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from time import perf_counter
from typing import Self

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.optimization.candidate_generator import CandidatePRP
from app.optimization.coverage import CoverageMatrix, DemandPoint, build_coverage_matrix
from app.optimization.risk_scoring import ShiftWindow


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"


class PRPOptimizerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    coverage_radius_meters: float = Field(gt=0)
    high_risk_threshold: float = Field(default=0.7, ge=0)
    objective_scale: int = Field(default=1_000_000, ge=1, le=1_000_000_000)
    maximum_solve_seconds: float = Field(default=10.0, gt=0, le=300)
    random_seed: int = Field(default=0, ge=0)
    optimizer_version: str = Field(default="weighted-max-coverage-v1", min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_finite_values(self) -> Self:
        if not math.isfinite(self.coverage_radius_meters):
            raise ValueError("coverage radius must be finite")
        if not math.isfinite(self.high_risk_threshold):
            raise ValueError("high-risk threshold must be finite")
        if not math.isfinite(self.maximum_solve_seconds):
            raise ValueError("maximum solve time must be finite")
        return self


class OptimizationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    optimizer_version: str
    candidate_count: int
    demand_count: int
    selected_count: int
    available_patrol_count: int
    coverage_radius_meters: float
    high_risk_threshold: float
    objective_scale: int
    shift_start: datetime
    shift_end: datetime
    solve_time_seconds: float


class PRPOptimizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    selected_prps: tuple[CandidatePRP, ...]
    covered_demand_ids: tuple[str, ...]
    covered_weighted_risk: float
    total_weighted_risk: float
    coverage_percentage: float = Field(ge=0, le=100)
    uncovered_high_risk_points: tuple[DemandPoint, ...]
    solver_status: SolverStatus
    metadata: OptimizationMetadata


def _empty_result(
    *,
    candidates: list[CandidatePRP],
    demands: list[DemandPoint],
    available_patrol_count: int,
    shift: ShiftWindow,
    config: PRPOptimizerConfig,
) -> PRPOptimizationResult:
    total = math.fsum(item.risk_weight for item in demands)
    return PRPOptimizationResult(
        selected_prps=(),
        covered_demand_ids=(),
        covered_weighted_risk=0,
        total_weighted_risk=total,
        coverage_percentage=0,
        uncovered_high_risk_points=tuple(
            item for item in demands if item.risk_weight >= config.high_risk_threshold
        ),
        solver_status=SolverStatus.NOT_RUN,
        metadata=OptimizationMetadata(
            optimizer_version=config.optimizer_version,
            candidate_count=len(candidates),
            demand_count=len(demands),
            selected_count=0,
            available_patrol_count=available_patrol_count,
            coverage_radius_meters=config.coverage_radius_meters,
            high_risk_threshold=config.high_risk_threshold,
            objective_scale=config.objective_scale,
            shift_start=shift.start,
            shift_end=shift.end,
            solve_time_seconds=0,
        ),
    )


def optimize_prps(
    candidates: list[CandidatePRP],
    demand_points: list[DemandPoint],
    *,
    available_patrol_count: int,
    shift: ShiftWindow,
    config: PRPOptimizerConfig,
) -> PRPOptimizationResult:
    """Select a capacity-bounded set maximizing unique covered demand risk."""
    if available_patrol_count < 0:
        raise ValueError("available_patrol_count cannot be negative")
    ordered_candidates = sorted(candidates, key=lambda item: item.candidate_id)
    ordered_demands = sorted(demand_points, key=lambda item: item.demand_id)
    matrix = build_coverage_matrix(
        ordered_candidates, ordered_demands, config.coverage_radius_meters
    )
    if available_patrol_count == 0 or not ordered_candidates or not ordered_demands:
        return _empty_result(
            candidates=ordered_candidates,
            demands=ordered_demands,
            available_patrol_count=available_patrol_count,
            shift=shift,
            config=config,
        )

    integer_weights = [
        max(1, round(item.risk_weight * config.objective_scale))
        if item.risk_weight > 0
        else 0
        for item in ordered_demands
    ]
    maximum_penalty = sum(
        len(ordered_candidates) + 1 + index
        for index in range(len(ordered_candidates))
    )
    primary_multiplier = maximum_penalty + 1
    maximum_objective = sum(integer_weights) * primary_multiplier + maximum_penalty
    if maximum_objective > 9_000_000_000_000_000_000:
        raise ValueError(
            "scaled objective exceeds the CP-SAT integer range; reduce objective_scale or input size"
        )
    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"candidate_{index}") for index in range(len(ordered_candidates))]
    covered = [model.new_bool_var(f"demand_{index}") for index in range(len(ordered_demands))]
    model.add(sum(selected) <= available_patrol_count)
    for demand_index, covering_candidates in enumerate(matrix.candidates_by_demand):
        if not covering_candidates:
            model.add(covered[demand_index] == 0)
            continue
        covering_sum = sum(selected[index] for index in covering_candidates)
        model.add(covered[demand_index] <= covering_sum)
        model.add(covering_sum <= len(covering_candidates) * covered[demand_index])

    primary = sum(integer_weights[index] * covered[index] for index in range(len(covered)))
    selection_penalty = sum(
        (len(ordered_candidates) + 1 + index) * variable
        for index, variable in enumerate(selected)
    )
    model.maximize(primary * primary_multiplier - selection_penalty)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.maximum_solve_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = config.random_seed
    started = perf_counter()
    status_code = solver.solve(model)
    elapsed = perf_counter() - started
    status_map = {
        cp_model.OPTIMAL: SolverStatus.OPTIMAL,
        cp_model.FEASIBLE: SolverStatus.FEASIBLE,
        cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
        cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
        cp_model.UNKNOWN: SolverStatus.UNKNOWN,
    }
    solver_status = status_map.get(status_code, SolverStatus.UNKNOWN)
    has_solution = solver_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    selected_indexes = (
        [index for index, variable in enumerate(selected) if solver.value(variable)]
        if has_solution
        else []
    )
    covered_indexes = {
        demand_index
        for candidate_index in selected_indexes
        for demand_index in matrix.demands_by_candidate[candidate_index]
    }
    covered_risk = math.fsum(ordered_demands[index].risk_weight for index in covered_indexes)
    total_risk = math.fsum(item.risk_weight for item in ordered_demands)
    percentage = (covered_risk / total_risk * 100) if total_risk > 0 else 0.0
    return PRPOptimizationResult(
        selected_prps=tuple(ordered_candidates[index] for index in selected_indexes),
        covered_demand_ids=tuple(ordered_demands[index].demand_id for index in sorted(covered_indexes)),
        covered_weighted_risk=covered_risk,
        total_weighted_risk=total_risk,
        coverage_percentage=min(100.0, max(0.0, percentage)),
        uncovered_high_risk_points=tuple(
            demand
            for index, demand in enumerate(ordered_demands)
            if index not in covered_indexes and demand.risk_weight >= config.high_risk_threshold
        ),
        solver_status=solver_status,
        metadata=OptimizationMetadata(
            optimizer_version=config.optimizer_version,
            candidate_count=len(ordered_candidates),
            demand_count=len(ordered_demands),
            selected_count=len(selected_indexes),
            available_patrol_count=available_patrol_count,
            coverage_radius_meters=config.coverage_radius_meters,
            high_risk_threshold=config.high_risk_threshold,
            objective_scale=config.objective_scale,
            shift_start=shift.start,
            shift_end=shift.end,
            solve_time_seconds=elapsed,
        ),
    )
