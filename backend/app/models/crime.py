"""Crime incident persistence model."""

from datetime import datetime

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, Index, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CrimeIncidentStatus


class CrimeIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Validated crime event used as a source for later risk analysis."""

    __tablename__ = "crime_incidents"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 5", name="severity_range"),
        Index("ix_crime_incidents_type_occurred", "crime_type", "occurred_at"),
        Index("ix_crime_incidents_status_reported", "status", "reported_at"),
        Index("ix_crime_incidents_location_gist", "location", postgresql_using="gist"),
    )

    crime_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ward: Mapped[str | None] = mapped_column(String(120), index=True)
    area: Mapped[str | None] = mapped_column(String(180), index=True)
    status: Mapped[CrimeIncidentStatus] = mapped_column(
        SAEnum(CrimeIncidentStatus, name="crime_incident_status", native_enum=True),
        nullable=False,
        default=CrimeIncidentStatus.REPORTED,
        server_default=CrimeIncidentStatus.REPORTED.value,
        index=True,
    )
