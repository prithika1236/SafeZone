"""ADMIN and POLICE patrol-assignment endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin, require_police
from app.database.dependencies import get_db_session
from app.models.enums import AssignmentStatus
from app.models.user import User
from app.schemas.assignment import (
    AssignmentBatchResponse,
    AssignmentList,
    AssignmentResponse,
    AutomaticAssignmentRequest,
    ManualAssignmentOverride,
)
from app.services.assignment_service import (
    AssignmentConflictError,
    AssignmentNotFoundError,
    InvalidAssignmentStateError,
    create_automatic_assignments,
    current_police_assignment,
    get_assignment,
    list_assignments,
    override_assignment,
    transition_assignment,
)

router = APIRouter(prefix="/patrols/assignments", tags=["patrol assignments"])
Admin = Annotated[User, Depends(require_admin)]
Police = Annotated[User, Depends(require_police)]
Session = Annotated[AsyncSession, Depends(get_db_session)]


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AssignmentNotFoundError):
        return HTTPException(status_code=404, detail=str(exc) or "Assignment not found")
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/automatic", response_model=AssignmentBatchResponse, status_code=status.HTTP_201_CREATED)
async def automatic(data: AutomaticAssignmentRequest, session: Session, _: Admin) -> AssignmentBatchResponse:
    try:
        return await create_automatic_assignments(session, data.optimization_run_id)
    except (AssignmentNotFoundError, AssignmentConflictError, InvalidAssignmentStateError) as exc:
        raise _service_error(exc) from exc


@router.get("", response_model=AssignmentList)
async def list_all(
    session: Session,
    _: Admin,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssignmentList:
    return await list_assignments(session, limit=limit, offset=offset)


@router.get("/current", response_model=AssignmentResponse)
async def current(session: Session, user: Police) -> AssignmentResponse:
    try:
        return await current_police_assignment(session, user.id)
    except AssignmentNotFoundError as exc:
        raise _service_error(exc) from exc


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def inspect(assignment_id: UUID, session: Session, _: Admin) -> AssignmentResponse:
    try:
        return await get_assignment(session, assignment_id)
    except AssignmentNotFoundError as exc:
        raise _service_error(exc) from exc


@router.patch("/{assignment_id}/override", response_model=AssignmentResponse)
async def override(
    assignment_id: UUID, data: ManualAssignmentOverride, session: Session, _: Admin
) -> AssignmentResponse:
    try:
        return await override_assignment(session, assignment_id, data)
    except (AssignmentNotFoundError, AssignmentConflictError, InvalidAssignmentStateError) as exc:
        raise _service_error(exc) from exc


@router.post("/{assignment_id}/cancel", response_model=AssignmentResponse)
async def cancel(assignment_id: UUID, session: Session, _: Admin) -> AssignmentResponse:
    try:
        return await transition_assignment(
            session, assignment_id, user_id=None, target_status=AssignmentStatus.CANCELLED
        )
    except (AssignmentNotFoundError, InvalidAssignmentStateError) as exc:
        raise _service_error(exc) from exc


async def _police_transition(
    assignment_id: UUID, session: AsyncSession, user: User, target: AssignmentStatus
) -> AssignmentResponse:
    try:
        return await transition_assignment(
            session, assignment_id, user_id=user.id, target_status=target
        )
    except (AssignmentNotFoundError, InvalidAssignmentStateError) as exc:
        raise _service_error(exc) from exc


@router.post("/{assignment_id}/acknowledge", response_model=AssignmentResponse)
async def acknowledge(assignment_id: UUID, session: Session, user: Police) -> AssignmentResponse:
    return await _police_transition(assignment_id, session, user, AssignmentStatus.ACKNOWLEDGED)


@router.post("/{assignment_id}/arrive", response_model=AssignmentResponse)
async def arrive(assignment_id: UUID, session: Session, user: Police) -> AssignmentResponse:
    return await _police_transition(assignment_id, session, user, AssignmentStatus.AT_PRP)


@router.post("/{assignment_id}/complete", response_model=AssignmentResponse)
async def complete(assignment_id: UUID, session: Session, user: Police) -> AssignmentResponse:
    return await _police_transition(assignment_id, session, user, AssignmentStatus.COMPLETED)

