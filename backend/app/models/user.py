"""Identity and citizen-owned contact persistence models."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.police import PoliceOfficer
    from app.models.sos import SOSRequest


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Authenticated SafeZone identity shared by all roles."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    police_officer: Mapped["PoliceOfficer | None"] = relationship(
        back_populates="user", uselist=False
    )
    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    sos_requests: Mapped[list["SOSRequest"]] = relationship(back_populates="citizen")


class EmergencyContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Private emergency contact owned by a SafeZone user."""

    __tablename__ = "emergency_contacts"
    __table_args__ = (Index("ix_emergency_contacts_owner_active", "owner_id", "is_active"),)

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    relationship_label: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    owner: Mapped[User] = relationship(back_populates="emergency_contacts")


Index("uq_users_email_lower", func.lower(User.email), unique=True)
