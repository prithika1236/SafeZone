"""Add crime audit and idempotent ingestion fields.

Revision ID: 20260825_0003
Revises: 20260825_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20260825_0003"
down_revision = "20260825_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crime_incidents", sa.Column("source_reference", sa.String(160), nullable=True))
    op.add_column("crime_incidents", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_unique_constraint("uq_crime_incidents_source_reference", "crime_incidents", ["source_reference"])


def downgrade() -> None:
    op.drop_constraint("uq_crime_incidents_source_reference", "crime_incidents", type_="unique")
    op.drop_column("crime_incidents", "updated_at")
    op.drop_column("crime_incidents", "source_reference")
