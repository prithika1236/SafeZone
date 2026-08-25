"""Database URL helpers for infrastructure configuration."""


def escape_alembic_url(database_url: str) -> str:
    """Escape percent signs consumed by Alembic's ConfigParser layer."""
    return database_url.replace("%", "%%")
