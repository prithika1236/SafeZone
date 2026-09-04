from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.database.base import Base
import app.models  # noqa: F401  Ensures model metadata is registered independently.

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260820_0001_database_foundation.py"
)
AUTH_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260825_0002_auth_email_uniqueness.py"
)
CRIME_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260825_0003_crime_management.py"
)
ASSIGNMENT_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260904_0004_patrol_assignment.py"
)


def test_initial_migration_matches_model_table_scope() -> None:
    spec = spec_from_file_location("safezone_initial_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260820_0001"
    assert migration.down_revision is None
    assert set(Base.metadata.tables) == {
        "users",
        "police_officers",
        "patrol_units",
        "crime_incidents",
        "optimization_runs",
        "prp_locations",
        "patrol_assignments",
        "sos_requests",
        "location_updates",
        "emergency_contacts",
        "risk_scores",
    }


def test_migration_enables_postgis_and_spatial_indexes() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS postgis" in source
    assert source.count('postgresql_using="gist"') == 5


def test_auth_migration_follows_database_foundation() -> None:
    spec = spec_from_file_location("safezone_auth_migration", AUTH_MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260825_0002"
    assert migration.down_revision == "20260820_0001"
    assert "lower(email)" in AUTH_MIGRATION_PATH.read_text(encoding="utf-8")


def test_crime_migration_follows_authentication() -> None:
    spec = spec_from_file_location("safezone_crime_migration", CRIME_MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260825_0003"
    assert migration.down_revision == "20260825_0002"
    source = CRIME_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "source_reference" in source
    assert "updated_at" in source


def test_assignment_migration_follows_crime_management() -> None:
    spec = spec_from_file_location("safezone_assignment_migration", ASSIGNMENT_MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260904_0004"
    assert migration.down_revision == "20260825_0003"
    source = ASSIGNMENT_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "ACKNOWLEDGED" in source
    assert source.count("EXCLUDE USING gist") == 2
