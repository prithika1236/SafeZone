"""Small process-local broker for active SOS WebSocket subscribers."""

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class SOSConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, socket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(socket)

    async def disconnect(self, user_id: UUID, socket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].discard(socket)
            if not self._connections[user_id]:
                self._connections.pop(user_id, None)

    async def publish(self, user_id: UUID, payload: dict[str, str]) -> None:
        async with self._lock:
            sockets = tuple(self._connections.get(user_id, ()))
        failed: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                failed.append(socket)
        for socket in failed:
            await self.disconnect(user_id, socket)


sos_connections = SOSConnectionManager()

