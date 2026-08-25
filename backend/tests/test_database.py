from alembic.config import Config
from geoalchemy2 import Geography
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers

from app.core.config import Settings
from app.database.base import Base
from app.database.session import create_database_engine
from app.database.url import escape_alembic_url
from app.models import SOSStatus

EXPECTED_TABLES = {
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

GEOSPATIAL_TABLES = {
    "crime_incidents",
    "prp_locations",
    "sos_requests",
    "location_updates",
    "risk_scores",
}


def test_all_model_relationships_configure() -> None:
    configure_mappers()


def test_metadata_contains_normalized_domain_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_geospatial_entities_use_postgis_points_without_duplicate_coordinates() -> None:
    for table_name in GEOSPATIAL_TABLES:
        table = Base.metadata.tables[table_name]

        assert isinstance(table.c.location.type, Geography)
        assert table.c.location.type.geometry_type == "POINT"
        assert table.c.location.type.srid == 4326
        assert "latitude" not in table.c
        assert "longitude" not in table.c
        assert any(
            index.dialect_options["postgresql"].get("using") == "gist"
            for index in table.indexes
        )


def test_metadata_compiles_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for table in Base.metadata.sorted_tables:
        compiled = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in compiled


def test_async_engine_is_postgresql_oriented() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://safezone:test@localhost:5432/safezone_test",
    )
    engine = create_database_engine(settings)

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.dialect.name == "postgresql"


def test_sos_statuses_cover_the_required_lifecycle() -> None:
    assert [status.value for status in SOSStatus] == [
        "PENDING",
        "ASSIGNED",
        "ACCEPTED",
        "EN_ROUTE",
        "ARRIVED",
        "RESOLVED",
        "CANCELLED",
    ]


def test_alembic_url_escapes_encoded_password_percent_signs() -> None:
    database_url = (
        "postgresql+asyncpg://safezone_user:example%40password@localhost:5432/safezone"
    )
    config = Config()

    config.set_main_option("sqlalchemy.url", escape_alembic_url(database_url))

    assert config.get_main_option("sqlalchemy.url") == database_url
