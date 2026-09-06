"""Push and emergency-contact notification provider abstractions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationMessage:
    title: str
    body: str
    data: dict[str, str]


class PushNotificationAdapter(Protocol):
    async def send(self, tokens: list[str], message: NotificationMessage) -> None: ...


class DevelopmentPushAdapter:
    """Safe local adapter: records no token or operational coordinate in logs."""
    async def send(self, tokens: list[str], message: NotificationMessage) -> None:
        logger.info("development_push", extra={"recipient_count": len(tokens), "event": message.data.get("event")})


class FirebasePushAdapter:
    def __init__(self, project_id: str, credentials_path: str) -> None:
        if not Path(credentials_path).is_file():
            raise ValueError("Firebase credentials file does not exist")
        try:
            import firebase_admin
            from firebase_admin import credentials
            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(credentials.Certificate(credentials_path), {"projectId": project_id})
        except ImportError as exc:
            raise RuntimeError("firebase-admin is required for Firebase notifications") from exc

    async def send(self, tokens: list[str], message: NotificationMessage) -> None:
        if not tokens:
            return
        from firebase_admin import messaging
        payload = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=message.title, body=message.body),
            data=message.data,
        )
        await asyncio.to_thread(messaging.send_each_for_multicast, payload)


def build_push_adapter(settings: Settings) -> PushNotificationAdapter:
    configured = settings.firebase_project_id and settings.firebase_credentials_path
    if settings.notification_adapter == "firebase" and not configured:
        raise ValueError("Firebase adapter requires project ID and credentials path")
    if settings.notification_adapter == "firebase" or (
        settings.notification_adapter == "auto" and configured
    ):
        return FirebasePushAdapter(settings.firebase_project_id or "", settings.firebase_credentials_path or "")
    return DevelopmentPushAdapter()


class EmergencyContactAdapter(Protocol):
    async def notify(self, destination: str, message: str) -> None: ...


class UnconfiguredEmergencyContactAdapter:
    async def notify(self, destination: str, message: str) -> None:
        logger.info("emergency_contact_provider_unconfigured")


async def safely_send_push(
    adapter: PushNotificationAdapter, tokens: list[str], message: NotificationMessage
) -> None:
    try:
        await adapter.send(tokens, message)
    except Exception:
        logger.exception("push_delivery_failed", extra={"event": message.data.get("event")})
