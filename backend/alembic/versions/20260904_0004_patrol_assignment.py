"""Add Stage 9 patrol-assignment lifecycle and overlap protection.

Revision ID: 20260904_0004
Revises: 20260825_0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260904_0004"
down_revision: str | None = "20260825_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires newly added enum values to be committed before constraints use them.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'ASSIGNED'")
        op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'ACKNOWLEDGED'")
        op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'AT_PRP'")
        op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'UNAVAILABLE'")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE patrol_assignments
        ADD CONSTRAINT ex_patrol_assignments_unit_shift_active
        EXCLUDE USING gist (
            patrol_unit_id WITH =,
            tstzrange(shift_start, shift_end, '[)') WITH &&
        ) WHERE (status IN ('PLANNED', 'ACTIVE', 'ASSIGNED', 'ACKNOWLEDGED', 'AT_PRP'))
        """
    )
    op.execute(
        """
        ALTER TABLE patrol_assignments
        ADD CONSTRAINT ex_patrol_assignments_officer_shift_active
        EXCLUDE USING gist (
            police_officer_id WITH =,
            tstzrange(shift_start, shift_end, '[)') WITH &&
        ) WHERE (status IN ('PLANNED', 'ACTIVE', 'ASSIGNED', 'ACKNOWLEDGED', 'AT_PRP'))
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ex_patrol_assignments_officer_shift_active",
        "patrol_assignments",
        type_="exclude",
    )
    op.drop_constraint(
        "ex_patrol_assignments_unit_shift_active",
        "patrol_assignments",
        type_="exclude",
    )
    # PostgreSQL enum values are intentionally retained to avoid unsafe type recreation.
