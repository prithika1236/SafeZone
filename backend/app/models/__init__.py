"""SafeZone SQLAlchemy models imported for metadata and Alembic discovery."""

from app.models.assignment import PatrolAssignment
from app.models.crime import CrimeIncident
from app.models.enums import (
    AssignmentStatus,
    CrimeIncidentStatus,
    OfficerAvailability,
    OptimizationRunStatus,
    PatrolUnitStatus,
    PRPStatus,
    SOSStatus,
    UserRole,
)
from app.models.location import LocationUpdate
from app.models.notification import DeviceRegistration
from app.models.optimization import OptimizationRun, PRPLocation, RiskScore
from app.models.police import PatrolUnit, PoliceOfficer
from app.models.sos import SOSRequest
from app.models.user import EmergencyContact, User

__all__ = [
    "AssignmentStatus",
    "CrimeIncident",
    "CrimeIncidentStatus",
    "EmergencyContact",
    "LocationUpdate",
    "DeviceRegistration",
    "OfficerAvailability",
    "OptimizationRun",
    "OptimizationRunStatus",
    "PRPLocation",
    "PRPStatus",
    "PatrolAssignment",
    "PatrolUnit",
    "PatrolUnitStatus",
    "PoliceOfficer",
    "RiskScore",
    "SOSRequest",
    "SOSStatus",
    "User",
    "UserRole",
]
