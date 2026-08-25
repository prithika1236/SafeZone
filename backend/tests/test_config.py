import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.backend_host == "127.0.0.1"
    assert settings.backend_port == 8000
    assert [str(origin) for origin in settings.allowed_frontend_origins] == [
        "http://localhost:5173/"
    ]


def test_invalid_backend_port_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKEND_PORT=70000)


def test_postgresql_database_url_is_required() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL must use PostgreSQL"):
        Settings(_env_file=None, DATABASE_URL="sqlite+aiosqlite:///test.db")

    with pytest.raises(ValidationError, match="asyncpg driver"):
        Settings(_env_file=None, DATABASE_URL="postgresql://safezone:test@localhost/safezone")
