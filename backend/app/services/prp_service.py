"""Transactional orchestration for strategic PRP optimization and approval."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geometry, WKTElement
from sqlalchemy import cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OptimizationRunStatus, PRPStatus
from app.models.optimization import OptimizationRun, PRPLocation
from app.optimization.coverage import build_coverage_matrix
from app.optimization.prp_optimizer import PRPOptimizationResult, SolverStatus, optimize_prps
from app.schemas.prp import OptimizationRunDetail, PRPOptimizationRequest, StoredPRPLocation


class OptimizationRunNotFoundError(Exception):
    pass


class InvalidOptimizationStateError(Exception):
    pass


async def preview_optimization(data: PRPOptimizationRequest) -> PRPOptimizationResult:
    """Run the CPU-bound solver without creating database records."""
    return await asyncio.to_thread(
        optimize_prps,
        data.candidates,
        data.demand_points,
        available_patrol_count=data.available_patrol_count,
        shift=data.shift,
        config=data.optimizer_config(),
    )


def _point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def _allocation_metadata(
    data: PRPOptimizationRequest, result: PRPOptimizationResult
) -> dict[str, tuple[tuple[str, ...], float]]:
    """Assign each covered demand to one selected PRP for auditable, unique totals."""
    selected = sorted(result.selected_prps, key=lambda item: item.candidate_id)
    matrix = build_coverage_matrix(selected, data.demand_points, data.coverage_radius_meters)
    assigned: dict[str, list[str]] = {item.candidate_id: [] for item in selected}
    covered_risk: dict[str, float] = {item.candidate_id: 0.0 for item in selected}
    ordered_demands = sorted(data.demand_points, key=lambda item: item.demand_id)
    for demand_index, candidate_indexes in enumerate(matrix.candidates_by_demand):
        if not candidate_indexes:
            continue
        owner = selected[candidate_indexes[0]].candidate_id
        demand = ordered_demands[demand_index]
        assigned[owner].append(demand.demand_id)
        covered_risk[owner] += demand.risk_weight
    return {
        candidate_id: (tuple(demand_ids), covered_risk[candidate_id])
        for candidate_id, demand_ids in assigned.items()
    }


async def generate_optimization(
    session: AsyncSession, data: PRPOptimizationRequest
) -> OptimizationRunDetail:
    """Persist one reproducible run and its unapproved candidate PRPs."""
    run = OptimizationRun(
        parameters={"request": data.model_dump(mode="json")},
        available_patrol_count=data.available_patrol_count,
        coverage_radius_meters=Decimal(str(data.coverage_radius_meters)),
        status=OptimizationRunStatus.RUNNING,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id
    try:
        result = await preview_optimization(data)
        allocations = _allocation_metadata(data, result)
        run.parameters = {
            "request": data.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        }
        unsuccessful = result.solver_status in {
            SolverStatus.INFEASIBLE,
            SolverStatus.MODEL_INVALID,
            SolverStatus.UNKNOWN,
        }
        run.status = (
            OptimizationRunStatus.FAILED if unsuccessful else OptimizationRunStatus.COMPLETED
        )
        run.failure_reason = (
            f"Optimizer finished without a usable solution: {result.solver_status}"
            if unsuccessful
            else None
        )
        for candidate in (() if unsuccessful else result.selected_prps):
            assigned_ids, covered_risk = allocations[candidate.candidate_id]
            session.add(
                PRPLocation(
                    optimization_run_id=run.id,
                    location=_point(candidate.location.latitude, candidate.location.longitude),
                    risk_score=Decimal(str(candidate.local_risk)),
                    covered_risk=Decimal(str(covered_risk)),
                    coverage_radius_meters=Decimal(str(data.coverage_radius_meters)),
                    coverage_metadata={
                        "candidate_id": candidate.candidate_id,
                        "candidate_metadata": candidate.metadata.model_dump(mode="json"),
                        "assigned_demand_ids": list(assigned_ids),
                    },
                    shift_start=data.shift.start,
                    shift_end=data.shift.end,
                    status=PRPStatus.CANDIDATE,
                )
            )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        await session.execute(
            update(OptimizationRun)
            .where(OptimizationRun.id == run_id)
            .values(
                status=OptimizationRunStatus.FAILED,
                failure_reason=str(exc)[:500],
            )
        )
        await session.commit()
        raise
    return await get_optimization_run(session, run_id)


def _location_query():
    geometry = cast(PRPLocation.location, Geometry(geometry_type="POINT", srid=4326))
    return select(PRPLocation, func.ST_X(geometry), func.ST_Y(geometry))


def _stored_prp(row) -> StoredPRPLocation:
    location, longitude, latitude = row
    return StoredPRPLocation(
        id=location.id,
        optimization_run_id=location.optimization_run_id,
        candidate_id=location.coverage_metadata["candidate_id"],
        location={"latitude": latitude, "longitude": longitude},
        risk_score=float(location.risk_score),
        covered_risk=float(location.covered_risk or 0),
        coverage_radius_meters=float(location.coverage_radius_meters),
        shift_start=location.shift_start,
        shift_end=location.shift_end,
        generated_at=location.generated_at,
        status=location.status,
        coverage_metadata=location.coverage_metadata,
    )


async def get_optimization_run(session: AsyncSession, run_id: UUID) -> OptimizationRunDetail:
    run = await session.scalar(select(OptimizationRun).where(OptimizationRun.id == run_id))
    if run is None:
        raise OptimizationRunNotFoundError
    rows = (
        await session.execute(
            _location_query()
            .where(PRPLocation.optimization_run_id == run_id)
            .order_by(PRPLocation.generated_at, PRPLocation.id)
        )
    ).all()
    serialized_result = run.parameters.get("result")
    return OptimizationRunDetail(
        id=run.id,
        run_at=run.run_at,
        available_patrol_count=run.available_patrol_count,
        coverage_radius_meters=float(run.coverage_radius_meters),
        status=run.status,
        failure_reason=run.failure_reason,
        result=PRPOptimizationResult.model_validate(serialized_result)
        if serialized_result
        else None,
        prp_locations=tuple(_stored_prp(row) for row in rows),
    )


async def approve_optimization_run(
    session: AsyncSession, run_id: UUID
) -> OptimizationRunDetail:
    run = await session.scalar(select(OptimizationRun).where(OptimizationRun.id == run_id))
    if run is None:
        raise OptimizationRunNotFoundError
    if run.status != OptimizationRunStatus.COMPLETED:
        raise InvalidOptimizationStateError("Only completed optimization runs can be approved")
    locations = (
        await session.scalars(select(PRPLocation).where(PRPLocation.optimization_run_id == run_id))
    ).all()
    if not locations:
        raise InvalidOptimizationStateError("This optimization run has no generated PRPs")
    if any(item.status not in (PRPStatus.CANDIDATE, PRPStatus.APPROVED) for item in locations):
        raise InvalidOptimizationStateError("Only candidate PRPs can be approved")
    for location in locations:
        location.status = PRPStatus.APPROVED
    await session.commit()
    return await get_optimization_run(session, run_id)


async def activate_optimization_run(
    session: AsyncSession, run_id: UUID
) -> OptimizationRunDetail:
    run = await session.scalar(select(OptimizationRun).where(OptimizationRun.id == run_id))
    if run is None:
        raise OptimizationRunNotFoundError
    locations = (
        await session.scalars(select(PRPLocation).where(PRPLocation.optimization_run_id == run_id))
    ).all()
    if not locations or any(item.status != PRPStatus.APPROVED for item in locations):
        raise InvalidOptimizationStateError("All generated PRPs must be approved before activation")
    shift_start = min(item.shift_start for item in locations)
    shift_end = max(item.shift_end for item in locations)
    await session.execute(
        update(PRPLocation)
        .where(
            PRPLocation.status == PRPStatus.ACTIVE,
            PRPLocation.shift_start < shift_end,
            PRPLocation.shift_end > shift_start,
        )
        .values(status=PRPStatus.INACTIVE)
    )
    for location in locations:
        location.status = PRPStatus.ACTIVE
    await session.commit()
    return await get_optimization_run(session, run_id)


async def list_active_prps(session: AsyncSession) -> tuple[StoredPRPLocation, ...]:
    rows = (
        await session.execute(
            _location_query()
            .where(PRPLocation.status == PRPStatus.ACTIVE)
            .order_by(PRPLocation.shift_start, PRPLocation.id)
        )
    ).all()
    return tuple(_stored_prp(row) for row in rows)
