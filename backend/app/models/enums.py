"""Shared persisted domain enumerations."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    POLICE = "POLICE"
    CITIZEN = "CITIZEN"


class OfficerAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    OFF_DUTY = "OFF_DUTY"
    UNAVAILABLE = "UNAVAILABLE"


class PatrolUnitStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    OFF_DUTY = "OFF_DUTY"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class CrimeIncidentStatus(StrEnum):
    REPORTED = "REPORTED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    DISMISSED = "DISMISSED"


class PRPStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REJECTED = "REJECTED"


class OptimizationRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssignmentStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SOSStatus(StrEnum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
