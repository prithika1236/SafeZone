from datetime import UTC, datetime, timedelta

from app.services.live_service import is_update_interval_allowed


def test_location_interval_rejects_aggressive_update() -> None:
    now = datetime.now(UTC)
    assert not is_update_interval_allowed(now - timedelta(seconds=5), now, 15)


def test_location_interval_accepts_first_and_controlled_update() -> None:
    now = datetime.now(UTC)
    assert is_update_interval_allowed(None, now, 15)
    assert is_update_interval_allowed(now - timedelta(seconds=15), now, 15)
