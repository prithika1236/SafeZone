"""Real-time SOS request persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import SOSStatus

if TYPE_CHECKING:
    from app.models.location import LocationUpdate
    from app.models.police import PatrolUnit
    from app.models.user import User


class SOSRequest(UUIDPrimaryKeyMixin, Base):
    """Citizen emergency request, separate from strategic PRP optimization."""

    __tablename__ = "sos_requests"
    __table_args__ = (
        Index("ix_sos_requests_status_created", "status", "created_at"),
        Index("ix_sos_requests_citizen_created", "citizen_id", "created_at"),
        Index("ix_sos_requests_location_gist", "location", postgresql_using="gist"),
    )

    citizen_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_patrol_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patrol_units.id", ondelete="SET NULL"), index=True
    )
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    status: Mapped[SOSStatus] = mapped_column(
        SAEnum(SOSStatus, name="sos_status", native_enum=True),
        nullable=False,
        default=SOSStatus.PENDING,
        server_default=SOSStatus.PENDING.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responder_distance_meters: Mapped[float | None] = mapped_column(Numeric(12, 2))
    estimated_duration_seconds: Mapped[float | None] = mapped_column(Numeric(12, 2))
    distance_source: Mapped[str | None] = mapped_column(String(40))

    citizen: Mapped["User"] = relationship(back_populates="sos_requests")
    assigned_patrol_unit: Mapped["PatrolUnit | None"] = relationship(back_populates="sos_requests")
    location_updates: Mapped[list["LocationUpdate"]] = relationship(back_populates="sos_request")
