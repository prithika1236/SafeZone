"""Database coordination and optional persistence for explainable risk scoring."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.enums import CrimeIncidentStatus
from app.models.optimization import RiskScore
from app.optimization.risk_scoring import (
    RiskCandidate,
    RiskIncident,
    RiskModelConfig,
    RiskResult,
    ShiftWindow,
    calculate_candidate_risk,
)
from app.schemas.location import Coordinate
from app.services.location_service import incidents_within_radius


def risk_config_from_settings(settings: Settings) -> RiskModelConfig:
    """Build the validated, snapshot-ready model policy from environment settings."""
    return RiskModelConfig(
        frequency_weight=settings.risk_frequency_weight,
        severity_weight=settings.risk_severity_weight,
        recency_weight=settings.risk_recency_weight,
        time_weight=settings.risk_time_weight,
        recency_decay_lambda=settings.risk_recency_decay_lambda,
        frequency_saturation_count=settings.risk_frequency_saturation_count,
        time_relevance_floor=settings.risk_time_relevance_floor,
        severity_mapping=settings.risk_severity_mapping,
        model_version=settings.risk_model_version,
    )


async def calculate_location_risk(
    session: AsyncSession,
    *,
    candidate_id: str,
    location: Coordinate,
    incident_radius_meters: float,
    shift: ShiftWindow,
    as_of: datetime,
    config: RiskModelConfig,
) -> RiskResult:
    """Load eligible nearby incidents once and calculate one candidate's risk."""
    nearby = await incidents_within_radius(
        session,
        location,
        incident_radius_meters,
        statuses=(CrimeIncidentStatus.REPORTED, CrimeIncidentStatus.VERIFIED),
    )
    candidate = RiskCandidate(
        candidate_id=candidate_id,
        location=location,
        incidents=tuple(
            RiskIncident(
                severity=incident.severity,
                occurred_at=incident.occurred_at,
                crime_type=incident.crime_type,
            )
            for incident in nearby
        ),
    )
    return calculate_candidate_risk(candidate, shift, as_of=as_of, config=config)


async def persist_risk_result(
    session: AsyncSession,
    result: RiskResult,
    *,
    shift: ShiftWindow,
    config: RiskModelConfig,
    optimization_run_id: UUID | None = None,
) -> RiskScore:
    """Persist a requested result with inputs needed to explain and reproduce it."""
    record = RiskScore(
        optimization_run_id=optimization_run_id,
        location=WKTElement(
            f"POINT({result.location.longitude} {result.location.latitude})", srid=4326
        ),
        score=Decimal(str(result.total_risk)),
        components={
            "candidate_id": result.candidate_id,
            "raw_total_risk": result.raw_total_risk,
            "normalized_across_batch": result.normalized_across_batch,
            "components": result.components.model_dump(mode="json"),
            "shift": shift.model_dump(mode="json"),
            "configuration": config.model_dump(mode="json"),
        },
        model_version=result.model_version,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
