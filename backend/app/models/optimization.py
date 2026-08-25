"""Risk scoring and strategic PRP optimization persistence models."""

from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import OptimizationRunStatus, PRPStatus

if TYPE_CHECKING:
    from app.models.assignment import PatrolAssignment


class OptimizationRun(UUIDPrimaryKeyMixin, Base):
    """Auditable inputs and result state for a reproducible PRP run."""

    __tablename__ = "optimization_runs"
    __table_args__ = (
        CheckConstraint("available_patrol_count >= 0", name="available_patrol_count_nonnegative"),
        CheckConstraint("coverage_radius_meters > 0", name="coverage_radius_positive"),
        Index("ix_optimization_runs_status_run_at", "status", "run_at"),
    )

    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    available_patrol_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_radius_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OptimizationRunStatus] = mapped_column(
        SAEnum(OptimizationRunStatus, name="optimization_run_status", native_enum=True),
        nullable=False,
        default=OptimizationRunStatus.PENDING,
        server_default=OptimizationRunStatus.PENDING.value,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500))

    prp_locations: Mapped[list["PRPLocation"]] = relationship(
        back_populates="optimization_run", cascade="all, delete-orphan"
    )
    risk_scores: Mapped[list["RiskScore"]] = relationship(back_populates="optimization_run")


class PRPLocation(UUIDPrimaryKeyMixin, Base):
    """Dynamic patrol response point generated for a bounded time window."""

    __tablename__ = "prp_locations"
    __table_args__ = (
        CheckConstraint("coverage_radius_meters > 0", name="coverage_radius_positive"),
        CheckConstraint("shift_end > shift_start", name="shift_window_order"),
        CheckConstraint("risk_score >= 0", name="risk_score_nonnegative"),
        Index("ix_prp_locations_status_shift", "status", "shift_start", "shift_end"),
        Index("ix_prp_locations_location_gist", "location", postgresql_using="gist"),
    )

    optimization_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    covered_risk: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    coverage_radius_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    coverage_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    shift_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shift_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[PRPStatus] = mapped_column(
        SAEnum(PRPStatus, name="prp_status", native_enum=True),
        nullable=False,
        default=PRPStatus.CANDIDATE,
        server_default=PRPStatus.CANDIDATE.value,
        index=True,
    )

    optimization_run: Mapped[OptimizationRun] = relationship(back_populates="prp_locations")
    assignments: Mapped[list["PatrolAssignment"]] = relationship(back_populates="prp_location")


class RiskScore(UUIDPrimaryKeyMixin, Base):
    """Explainable computed risk value tied to its run and configuration."""

    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="normalized_score_range"),
        Index("ix_risk_scores_location_gist", "location", postgresql_using="gist"),
        Index("ix_risk_scores_run_calculated", "optimization_run_id", "calculated_at"),
    )

    optimization_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="SET NULL"), index=True
    )
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(8, 7), nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    optimization_run: Mapped[OptimizationRun | None] = relationship(back_populates="risk_scores")
