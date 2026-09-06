"""Scoped live-emergency communication endpoints."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_active_user, require_police
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.database.dependencies import get_db_session
from app.database.session import async_session_factory
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.live import (
    DeviceRegistrationCreate, DeviceRegistrationResponse,
    PoliceLocationAccepted, PoliceLocationCreate,
)
from app.services.live_service import (
    LiveLocationError, LocationRateLimitError, record_police_location, register_device,
)
from app.services.realtime_service import sos_connections

router = APIRouter(tags=["live emergency communication"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.post("/live/police/location", response_model=PoliceLocationAccepted)
async def police_location(
    data: PoliceLocationCreate, session: Session,
    police: Annotated[User, Depends(require_police)], settings: Configuration,
) -> PoliceLocationAccepted:
    try:
        update = await record_police_location(session, police, data, settings)
    except LocationRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LiveLocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PoliceLocationAccepted(
        id=update.id, recorded_at=update.recorded_at,
        minimum_interval_seconds=settings.police_location_minimum_interval_seconds,
    )


@router.post("/notifications/devices", response_model=DeviceRegistrationResponse)
async def device_registration(
    data: DeviceRegistrationCreate, session: Session,
    user: Annotated[User, Depends(get_current_active_user)],
) -> DeviceRegistrationResponse:
    await register_device(session, user, data)
    return DeviceRegistrationResponse()


@router.websocket("/ws/sos")
async def sos_events(socket: WebSocket) -> None:
    await socket.accept()
    user: User | None = None
    try:
        authentication = await asyncio.wait_for(socket.receive_json(), timeout=10)
        token = authentication.get("access_token") if isinstance(authentication, dict) else None
        if not isinstance(token, str):
            await socket.close(code=4401)
            return
        settings = socket.app.state.settings
        try:
            claims = decode_access_token(token, settings)
        except AuthenticationError:
            await socket.close(code=4401)
            return
        if claims.role not in (UserRole.CITIZEN, UserRole.POLICE):
            await socket.close(code=4403)
            return
        async with async_session_factory() as session:
            user = await session.scalar(select(User).where(User.id == claims.user_id))
        if user is None or not user.is_active or user.role != claims.role:
            await socket.close(code=4401)
            return
        await sos_connections.connect(user.id, socket)
        await socket.send_json({"event": "connected"})
        while True:
            await socket.receive_text()
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if user is not None:
            await sos_connections.disconnect(user.id, socket)
