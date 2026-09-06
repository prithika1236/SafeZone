"""Add device registrations for live emergency notifications.

Revision ID: 20260906_0006
Revises: 20260905_0005
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260906_0006"
down_revision: str | None = "20260905_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_registrations_token", "device_registrations", ["token"], unique=True)
    op.create_index("ix_device_registrations_user_active", "device_registrations", ["user_id", "is_active"])


def downgrade() -> None:
    op.drop_table("device_registrations")
