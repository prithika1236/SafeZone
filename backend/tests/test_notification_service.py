import asyncio

import pytest

from app.core.config import Settings
from app.services.notification_service import (
    DevelopmentPushAdapter, NotificationMessage, build_push_adapter,
    safely_send_push,
)


def settings(**values) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://safezone:test@localhost/safezone_test",
        JWT_SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
        **values,
    )


def test_development_adapter_is_safe_default() -> None:
    assert isinstance(build_push_adapter(settings()), DevelopmentPushAdapter)


def test_explicit_firebase_rejects_missing_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        build_push_adapter(settings(NOTIFICATION_ADAPTER="firebase"))


def test_delivery_failure_does_not_break_emergency_workflow() -> None:
    class BrokenAdapter:
        async def send(self, tokens, message):
            raise RuntimeError("provider offline")

    asyncio.run(safely_send_push(
        BrokenAdapter(), ["secret-device-token"],
        NotificationMessage("Status", "Updated", {"event": "status"}),
    ))
