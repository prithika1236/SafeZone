"""Police officer and patrol unit persistence models."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import OfficerAvailability, PatrolUnitStatus

if TYPE_CHECKING:
    from app.models.assignment import PatrolAssignment
    from app.models.location import LocationUpdate
    from app.models.sos import SOSRequest
    from app.models.user import User


class PoliceOfficer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Minimal operational police profile linked one-to-one with a user."""

    __tablename__ = "police_officers"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    badge_identifier: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    availability_status: Mapped[OfficerAvailability] = mapped_column(
        SAEnum(OfficerAvailability, name="officer_availability", native_enum=True),
        nullable=False,
        default=OfficerAvailability.OFF_DUTY,
        server_default=OfficerAvailability.OFF_DUTY.value,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="police_officer")
    assignments: Mapped[list["PatrolAssignment"]] = relationship(back_populates="officer")


class PatrolUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Deployable patrol resource independent of any permanent station."""

    __tablename__ = "patrol_units"
    __table_args__ = (Index("ix_patrol_units_status_identifier", "status", "unit_identifier"),)

    unit_identifier: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[PatrolUnitStatus] = mapped_column(
        SAEnum(PatrolUnitStatus, name="patrol_unit_status", native_enum=True),
        nullable=False,
        default=PatrolUnitStatus.OUT_OF_SERVICE,
        server_default=PatrolUnitStatus.OUT_OF_SERVICE.value,
        index=True,
    )

    assignments: Mapped[list["PatrolAssignment"]] = relationship(back_populates="patrol_unit")
    sos_requests: Mapped[list["SOSRequest"]] = relationship(back_populates="assigned_patrol_unit")
    location_updates: Mapped[list["LocationUpdate"]] = relationship(
        back_populates="patrol_unit", cascade="all, delete-orphan"
    )
