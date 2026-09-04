"""Validated environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, PositiveFloat, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """SafeZone runtime settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias="APP_ENV"
    )
    app_name: str = Field(default="SafeZone API", validation_alias="APP_NAME")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    backend_host: str = Field(default="127.0.0.1", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, ge=1, le=65535, validation_alias="BACKEND_PORT")
    allowed_frontend_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")],
        validation_alias="ALLOWED_FRONTEND_ORIGINS",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://safezone_user:change_me@localhost:5432/safezone",
        validation_alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, validation_alias="DATABASE_ECHO")
    database_pool_size: PositiveInt = Field(default=5, validation_alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(
        default=10, ge=0, validation_alias="DATABASE_MAX_OVERFLOW"
    )
    crime_csv_max_bytes: PositiveInt = Field(
        default=5_242_880, validation_alias="CRIME_CSV_MAX_BYTES"
    )

    jwt_secret_key: str = Field(
        default="development-only-placeholder-change-me",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256", validation_alias="JWT_ALGORITHM"
    )
    jwt_access_token_expire_minutes: PositiveInt = Field(
        default=30, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_issuer: str = Field(default="safezone-api", validation_alias="JWT_ISSUER")
    jwt_audience: str = Field(default="safezone-clients", validation_alias="JWT_AUDIENCE")

    firebase_project_id: str | None = Field(default=None, validation_alias="FIREBASE_PROJECT_ID")
    firebase_credentials_path: str | None = Field(
        default=None, validation_alias="FIREBASE_CREDENTIALS_PATH"
    )
    routing_service_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:5000"),
        validation_alias="ROUTING_SERVICE_BASE_URL",
    )
    routing_service_timeout_seconds: PositiveFloat = Field(
        default=5.0, validation_alias="ROUTING_SERVICE_TIMEOUT_SECONDS"
    )
    default_proximity_radius_meters: PositiveFloat = Field(
        default=3000.0, validation_alias="DEFAULT_PROXIMITY_RADIUS_METERS"
    )
    risk_frequency_weight: float = Field(default=0.25, ge=0, validation_alias="RISK_FREQUENCY_WEIGHT")
    risk_severity_weight: float = Field(default=0.30, ge=0, validation_alias="RISK_SEVERITY_WEIGHT")
    risk_recency_weight: float = Field(default=0.30, ge=0, validation_alias="RISK_RECENCY_WEIGHT")
    risk_time_weight: float = Field(default=0.15, ge=0, validation_alias="RISK_TIME_WEIGHT")
    risk_recency_decay_lambda: PositiveFloat = Field(
        default=0.05, validation_alias="RISK_RECENCY_DECAY_LAMBDA"
    )
    risk_frequency_saturation_count: PositiveFloat = Field(
        default=5.0, validation_alias="RISK_FREQUENCY_SATURATION_COUNT"
    )
    risk_time_relevance_floor: float = Field(
        default=0.25, ge=0, le=1, validation_alias="RISK_TIME_RELEVANCE_FLOOR"
    )
    risk_severity_mapping: dict[int, float] = Field(
        default_factory=lambda: {1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0},
        validation_alias="RISK_SEVERITY_MAPPING",
    )
    risk_model_version: str = Field(
        default="weighted-risk-v1", min_length=1, max_length=80,
        validation_alias="RISK_MODEL_VERSION",
    )

    @field_validator("allowed_frontend_origins")
    @classmethod
    def reject_wildcard_cors(cls, origins: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        """Prevent configuration from silently enabling unrestricted CORS."""
        if any(str(origin) == "*" for origin in origins):
            raise ValueError("Wildcard CORS origins are not allowed")
        return origins

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, database_url: str) -> str:
        """Keep production database configuration PostgreSQL/PostGIS-oriented."""
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with the asyncpg driver")
        return database_url

    @field_validator("jwt_secret_key")
    @classmethod
    def require_sufficient_jwt_secret(cls, secret: str) -> str:
        """Require enough entropy capacity for an HMAC signing secret."""
        if len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return secret


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""
    return Settings()
