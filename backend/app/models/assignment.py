"""Strategic patrol assignment persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import AssignmentStatus

if TYPE_CHECKING:
    from app.models.optimization import PRPLocation
    from app.models.police import PatrolUnit, PoliceOfficer


class PatrolAssignment(UUIDPrimaryKeyMixin, Base):
    """Connect an officer and patrol unit to an approved strategic PRP."""

    __tablename__ = "patrol_assignments"
    __table_args__ = (
        CheckConstraint("shift_end > shift_start", name="shift_window_order"),
        Index("ix_patrol_assignments_unit_shift", "patrol_unit_id", "shift_start", "shift_end"),
        Index("ix_patrol_assignments_officer_shift", "police_officer_id", "shift_start"),
        Index("ix_patrol_assignments_status_shift", "status", "shift_start"),
    )

    patrol_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("patrol_units.id", ondelete="RESTRICT"), nullable=False
    )
    police_officer_id: Mapped[UUID] = mapped_column(
        ForeignKey("police_officers.id", ondelete="RESTRICT"), nullable=False
    )
    prp_location_id: Mapped[UUID] = mapped_column(
        ForeignKey("prp_locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    shift_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shift_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status", native_enum=True),
        nullable=False,
        default=AssignmentStatus.PLANNED,
        server_default=AssignmentStatus.PLANNED.value,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    patrol_unit: Mapped["PatrolUnit"] = relationship(back_populates="assignments")
    officer: Mapped["PoliceOfficer"] = relationship(back_populates="assignments")
    prp_location: Mapped["PRPLocation"] = relationship(back_populates="assignments")
