"""ADMIN-only strategic patrol response point operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin
from app.database.dependencies import get_db_session
from app.models.user import User
from app.optimization.prp_optimizer import PRPOptimizationResult
from app.schemas.prp import OptimizationRunDetail, PRPOptimizationRequest, StoredPRPLocation
from app.services.prp_service import (
    InvalidOptimizationStateError,
    OptimizationRunNotFoundError,
    activate_optimization_run,
    approve_optimization_run,
    generate_optimization,
    get_optimization_run,
    list_active_prps,
    preview_optimization,
)

router = APIRouter(prefix="/prp", tags=["PRP optimization"])
Admin = Annotated[User, Depends(require_admin)]
Session = Annotated[AsyncSession, Depends(get_db_session)]


def _translate_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OptimizationRunNotFoundError):
        return HTTPException(status_code=404, detail="Optimization run not found")
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/preview", response_model=PRPOptimizationResult)
async def preview(data: PRPOptimizationRequest, _: Admin) -> PRPOptimizationResult:
    return await preview_optimization(data)


@router.post("/generate", response_model=OptimizationRunDetail, status_code=status.HTTP_201_CREATED)
async def generate(data: PRPOptimizationRequest, session: Session, _: Admin) -> OptimizationRunDetail:
    return await generate_optimization(session, data)


@router.get("/active", response_model=tuple[StoredPRPLocation, ...])
async def active(session: Session, _: Admin) -> tuple[StoredPRPLocation, ...]:
    return await list_active_prps(session)


@router.get("/runs/{run_id}", response_model=OptimizationRunDetail)
async def inspect(run_id: UUID, session: Session, _: Admin) -> OptimizationRunDetail:
    try:
        return await get_optimization_run(session, run_id)
    except OptimizationRunNotFoundError as exc:
        raise _translate_service_error(exc) from exc


@router.post("/runs/{run_id}/approve", response_model=OptimizationRunDetail)
async def approve(run_id: UUID, session: Session, _: Admin) -> OptimizationRunDetail:
    try:
        return await approve_optimization_run(session, run_id)
    except (OptimizationRunNotFoundError, InvalidOptimizationStateError) as exc:
        raise _translate_service_error(exc) from exc


@router.post("/runs/{run_id}/activate", response_model=OptimizationRunDetail)
async def activate(run_id: UUID, session: Session, _: Admin) -> OptimizationRunDetail:
    try:
        return await activate_optimization_run(session, run_id)
    except (OptimizationRunNotFoundError, InvalidOptimizationStateError) as exc:
        raise _translate_service_error(exc) from exc

