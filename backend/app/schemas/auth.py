"""Authentication request and response schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints, field_validator

from app.models.enums import UserRole

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]


class CitizenRegistration(BaseModel):
    """Public registration fields; role is intentionally not user-controlled."""

    name: DisplayName
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: EmailStr) -> str:
        return str(email).strip().casefold()


class UserProfile(BaseModel):
    """Authenticated profile response without sensitive fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccessTokenResponse(BaseModel):
    """OAuth2-compatible access token response."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
