"""Create the initial normalized PostgreSQL/PostGIS domain schema.

Revision ID: 20260820_0001
Revises: None
Create Date: 2026-08-20
"""

from collections.abc import Sequence

from alembic import op
from geoalchemy2 import Geography
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("ADMIN", "POLICE", "CITIZEN", name="user_role", create_type=False)
officer_availability = postgresql.ENUM(
    "AVAILABLE", "ASSIGNED", "OFF_DUTY", "UNAVAILABLE",
    name="officer_availability", create_type=False,
)
patrol_unit_status = postgresql.ENUM(
    "AVAILABLE", "ASSIGNED", "RESPONDING", "OFF_DUTY", "OUT_OF_SERVICE",
    name="patrol_unit_status", create_type=False,
)
crime_incident_status = postgresql.ENUM(
    "REPORTED", "VERIFIED", "CLOSED", "DISMISSED",
    name="crime_incident_status", create_type=False,
)
optimization_run_status = postgresql.ENUM(
    "PENDING", "RUNNING", "COMPLETED", "FAILED",
    name="optimization_run_status", create_type=False,
)
prp_status = postgresql.ENUM(
    "CANDIDATE", "APPROVED", "ACTIVE", "INACTIVE", "REJECTED",
    name="prp_status", create_type=False,
)
assignment_status = postgresql.ENUM(
    "PLANNED", "ACTIVE", "COMPLETED", "CANCELLED",
    name="assignment_status", create_type=False,
)
sos_status = postgresql.ENUM(
    "PENDING", "ASSIGNED", "ACCEPTED", "EN_ROUTE", "ARRIVED", "RESOLVED", "CANCELLED",
    name="sos_status", create_type=False,
)

ENUMS = (
    user_role,
    officer_availability,
    patrol_unit_status,
    crime_incident_status,
    optimization_run_status,
    prp_status,
    assignment_status,
    sos_status,
)


def upgrade() -> None:
    """Create PostGIS support, enums, tables, and query indexes."""
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_role_active", "users", ["role", "is_active"])

    op.create_table(
        "emergency_contacts",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("relationship_label", sa.String(80), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_emergency_contacts_owner_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_emergency_contacts"),
    )
    op.create_index("ix_emergency_contacts_owner_active", "emergency_contacts", ["owner_id", "is_active"])

    op.create_table(
        "police_officers",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("badge_identifier", sa.String(80), nullable=False),
        sa.Column("availability_status", officer_availability, server_default="OFF_DUTY", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_police_officers_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_police_officers"),
        sa.UniqueConstraint("badge_identifier", name="uq_police_officers_badge_identifier"),
        sa.UniqueConstraint("user_id", name="uq_police_officers_user_id"),
    )
    op.create_index("ix_police_officers_availability_status", "police_officers", ["availability_status"])
    op.create_index("ix_police_officers_badge_identifier", "police_officers", ["badge_identifier"])

    op.create_table(
        "patrol_units",
        sa.Column("unit_identifier", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=True),
        sa.Column("status", patrol_unit_status, server_default="OUT_OF_SERVICE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_patrol_units"),
        sa.UniqueConstraint("unit_identifier", name="uq_patrol_units_unit_identifier"),
    )
    op.create_index("ix_patrol_units_status", "patrol_units", ["status"])
    op.create_index("ix_patrol_units_status_identifier", "patrol_units", ["status", "unit_identifier"])
    op.create_index("ix_patrol_units_unit_identifier", "patrol_units", ["unit_identifier"])

    op.create_table(
        "crime_incidents",
        sa.Column("crime_type", sa.String(120), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ward", sa.String(120), nullable=True),
        sa.Column("area", sa.String(180), nullable=True),
        sa.Column("status", crime_incident_status, server_default="REPORTED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("severity BETWEEN 1 AND 5", name="ck_crime_incidents_severity_range"),
        sa.PrimaryKeyConstraint("id", name="pk_crime_incidents"),
    )
    op.create_index("ix_crime_incidents_area", "crime_incidents", ["area"])
    op.create_index("ix_crime_incidents_crime_type", "crime_incidents", ["crime_type"])
    op.create_index("ix_crime_incidents_location_gist", "crime_incidents", ["location"], postgresql_using="gist")
    op.create_index("ix_crime_incidents_occurred_at", "crime_incidents", ["occurred_at"])
    op.create_index("ix_crime_incidents_status", "crime_incidents", ["status"])
    op.create_index("ix_crime_incidents_status_reported", "crime_incidents", ["status", "reported_at"])
    op.create_index("ix_crime_incidents_type_occurred", "crime_incidents", ["crime_type", "occurred_at"])
    op.create_index("ix_crime_incidents_ward", "crime_incidents", ["ward"])

    op.create_table(
        "optimization_runs",
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("available_patrol_count", sa.Integer(), nullable=False),
        sa.Column("coverage_radius_meters", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", optimization_run_status, server_default="PENDING", nullable=False),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("available_patrol_count >= 0", name="ck_optimization_runs_available_patrol_count_nonnegative"),
        sa.CheckConstraint("coverage_radius_meters > 0", name="ck_optimization_runs_coverage_radius_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_optimization_runs"),
    )
    op.create_index("ix_optimization_runs_run_at", "optimization_runs", ["run_at"])
    op.create_index("ix_optimization_runs_status", "optimization_runs", ["status"])
    op.create_index("ix_optimization_runs_status_run_at", "optimization_runs", ["status", "run_at"])

    op.create_table(
        "prp_locations",
        sa.Column("optimization_run_id", sa.Uuid(), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("risk_score", sa.Numeric(12, 6), nullable=False),
        sa.Column("covered_risk", sa.Numeric(12, 6), nullable=True),
        sa.Column("coverage_radius_meters", sa.Numeric(10, 2), nullable=False),
        sa.Column("coverage_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("shift_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", prp_status, server_default="CANDIDATE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("coverage_radius_meters > 0", name="ck_prp_locations_coverage_radius_positive"),
        sa.CheckConstraint("risk_score >= 0", name="ck_prp_locations_risk_score_nonnegative"),
        sa.CheckConstraint("shift_end > shift_start", name="ck_prp_locations_shift_window_order"),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.id"], name="fk_prp_locations_optimization_run_id_optimization_runs", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_prp_locations"),
    )
    op.create_index("ix_prp_locations_location_gist", "prp_locations", ["location"], postgresql_using="gist")
    op.create_index("ix_prp_locations_optimization_run_id", "prp_locations", ["optimization_run_id"])
    op.create_index("ix_prp_locations_status", "prp_locations", ["status"])
    op.create_index("ix_prp_locations_status_shift", "prp_locations", ["status", "shift_start", "shift_end"])

    op.create_table(
        "risk_scores",
        sa.Column("optimization_run_id", sa.Uuid(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("score", sa.Numeric(8, 7), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_risk_scores_normalized_score_range"),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.id"], name="fk_risk_scores_optimization_run_id_optimization_runs", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_scores"),
    )
    op.create_index("ix_risk_scores_calculated_at", "risk_scores", ["calculated_at"])
    op.create_index("ix_risk_scores_location_gist", "risk_scores", ["location"], postgresql_using="gist")
    op.create_index("ix_risk_scores_optimization_run_id", "risk_scores", ["optimization_run_id"])
    op.create_index("ix_risk_scores_run_calculated", "risk_scores", ["optimization_run_id", "calculated_at"])

    op.create_table(
        "patrol_assignments",
        sa.Column("patrol_unit_id", sa.Uuid(), nullable=False),
        sa.Column("police_officer_id", sa.Uuid(), nullable=False),
        sa.Column("prp_location_id", sa.Uuid(), nullable=False),
        sa.Column("shift_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", assignment_status, server_default="PLANNED", nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("shift_end > shift_start", name="ck_patrol_assignments_shift_window_order"),
        sa.ForeignKeyConstraint(["patrol_unit_id"], ["patrol_units.id"], name="fk_patrol_assignments_patrol_unit_id_patrol_units", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["police_officer_id"], ["police_officers.id"], name="fk_patrol_assignments_police_officer_id_police_officers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prp_location_id"], ["prp_locations.id"], name="fk_patrol_assignments_prp_location_id_prp_locations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_patrol_assignments"),
    )
    op.create_index("ix_patrol_assignments_officer_shift", "patrol_assignments", ["police_officer_id", "shift_start"])
    op.create_index("ix_patrol_assignments_prp_location_id", "patrol_assignments", ["prp_location_id"])
    op.create_index("ix_patrol_assignments_status", "patrol_assignments", ["status"])
    op.create_index("ix_patrol_assignments_status_shift", "patrol_assignments", ["status", "shift_start"])
    op.create_index("ix_patrol_assignments_unit_shift", "patrol_assignments", ["patrol_unit_id", "shift_start", "shift_end"])

    op.create_table(
        "sos_requests",
        sa.Column("citizen_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_patrol_unit_id", sa.Uuid(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("status", sos_status, server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_patrol_unit_id"], ["patrol_units.id"], name="fk_sos_requests_assigned_patrol_unit_id_patrol_units", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["citizen_id"], ["users.id"], name="fk_sos_requests_citizen_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_sos_requests"),
    )
    op.create_index("ix_sos_requests_assigned_patrol_unit_id", "sos_requests", ["assigned_patrol_unit_id"])
    op.create_index("ix_sos_requests_citizen_created", "sos_requests", ["citizen_id", "created_at"])
    op.create_index("ix_sos_requests_location_gist", "sos_requests", ["location"], postgresql_using="gist")
    op.create_index("ix_sos_requests_status", "sos_requests", ["status"])
    op.create_index("ix_sos_requests_status_created", "sos_requests", ["status", "created_at"])

    op.create_table(
        "location_updates",
        sa.Column("patrol_unit_id", sa.Uuid(), nullable=False),
        sa.Column("sos_request_id", sa.Uuid(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("accuracy_meters", sa.Numeric(8, 2), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["patrol_unit_id"], ["patrol_units.id"], name="fk_location_updates_patrol_unit_id_patrol_units", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sos_request_id"], ["sos_requests.id"], name="fk_location_updates_sos_request_id_sos_requests", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_location_updates"),
    )
    op.create_index("ix_location_updates_location_gist", "location_updates", ["location"], postgresql_using="gist")
    op.create_index("ix_location_updates_patrol_recorded", "location_updates", ["patrol_unit_id", "recorded_at"])
    op.create_index("ix_location_updates_recorded_at", "location_updates", ["recorded_at"])
    op.create_index("ix_location_updates_sos_recorded", "location_updates", ["sos_request_id", "recorded_at"])


def downgrade() -> None:
    """Remove SafeZone-owned schema objects while preserving shared PostGIS."""
    for table_name in (
        "location_updates",
        "sos_requests",
        "patrol_assignments",
        "risk_scores",
        "prp_locations",
        "optimization_runs",
        "crime_incidents",
        "patrol_units",
        "police_officers",
        "emergency_contacts",
        "users",
    ):
        op.drop_table(table_name)

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=True)
