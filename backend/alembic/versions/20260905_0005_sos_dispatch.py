"""Add auditable SOS dispatch lifecycle metadata.

Revision ID: 20260905_0005
Revises: 20260904_0004
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260905_0005"
down_revision: str | None = "20260904_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("accepted_at", "en_route_at", "arrived_at", "resolved_at", "cancelled_at"):
        op.add_column("sos_requests", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column("sos_requests", sa.Column("responder_distance_meters", sa.Numeric(12, 2)))
    op.add_column("sos_requests", sa.Column("estimated_duration_seconds", sa.Numeric(12, 2)))
    op.add_column("sos_requests", sa.Column("distance_source", sa.String(40)))
    op.create_index(
        "ix_sos_requests_unit_status",
        "sos_requests",
        ["assigned_patrol_unit_id", "status"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sos_requests_citizen_open ON sos_requests (citizen_id) "
        "WHERE status IN ('PENDING','ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED')"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sos_requests_unit_open ON sos_requests (assigned_patrol_unit_id) "
        "WHERE assigned_patrol_unit_id IS NOT NULL AND "
        "status IN ('ASSIGNED','ACCEPTED','EN_ROUTE','ARRIVED')"
    )


def downgrade() -> None:
    op.drop_index("uq_sos_requests_unit_open", table_name="sos_requests")
    op.drop_index("uq_sos_requests_citizen_open", table_name="sos_requests")
    op.drop_index("ix_sos_requests_unit_status", table_name="sos_requests")
    for name in (
        "distance_source", "estimated_duration_seconds", "responder_distance_meters",
        "cancelled_at", "resolved_at", "arrived_at", "en_route_at", "accepted_at",
    ):
        op.drop_column("sos_requests", name)
