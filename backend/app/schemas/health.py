"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public API process-health response."""

    status: Literal["ok"]
    service: str
    message: str
