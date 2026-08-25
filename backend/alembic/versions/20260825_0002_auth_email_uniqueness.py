"""Enforce case-insensitive user email uniqueness.

Revision ID: 20260825_0002
Revises: 20260820_0001
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260825_0002"
down_revision: str | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Prevent duplicate emails that differ only by case."""
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    """Remove the case-insensitive uniqueness index."""
    op.drop_index("uq_users_email_lower", table_name="users")
