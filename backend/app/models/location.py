"""Operational location history persistence model."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.police import PatrolUnit
    from app.models.sos import SOSRequest


class LocationUpdate(UUIDPrimaryKeyMixin, Base):
    """Timestamped patrol location retained for an approved operational purpose."""

    __tablename__ = "location_updates"
    __table_args__ = (
        Index("ix_location_updates_patrol_recorded", "patrol_unit_id", "recorded_at"),
        Index("ix_location_updates_sos_recorded", "sos_request_id", "recorded_at"),
        Index("ix_location_updates_location_gist", "location", postgresql_using="gist"),
    )

    patrol_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("patrol_units.id", ondelete="CASCADE"), nullable=False
    )
    sos_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sos_requests.id", ondelete="SET NULL")
    )
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    patrol_unit: Mapped["PatrolUnit"] = relationship(back_populates="location_updates")
    sos_request: Mapped["SOSRequest | None"] = relationship(back_populates="location_updates")
