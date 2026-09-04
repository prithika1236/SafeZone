"""Service-layer persistence boundary tests for optimization generation."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.models.enums import OptimizationRunStatus, PRPStatus
from app.models.optimization import OptimizationRun, PRPLocation
from app.optimization.candidate_generator import CandidateMetadata, CandidatePRP
from app.optimization.coverage import DemandPoint
from app.optimization.risk_scoring import ShiftWindow
from app.schemas.location import Coordinate
from app.schemas.prp import PRPOptimizationRequest
from app.services import prp_service


class GenerationSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def refresh(self, run: OptimizationRun) -> None:
        run.id = uuid4()
        run.run_at = datetime.now(UTC)


def test_generate_persists_run_and_selected_candidate_prp(monkeypatch) -> None:
    point = Coordinate(latitude=12.9716, longitude=77.5946)
    candidate = CandidatePRP(
        candidate_id="safe-node-1",
        location=point,
        local_risk=0.8,
        metadata=CandidateMetadata(
            generation_method="safe_node_snap",
            generator_version="test-v1",
            source_area_ids=("area-1",),
            source_metadata={},
            evidence_count=2,
            calculated_centroid=point,
            operationally_verified=True,
            safe_node_id="node-1",
        ),
    )
    data = PRPOptimizationRequest(
        candidates=[candidate],
        demand_points=[DemandPoint(demand_id="risk-1", location=point, risk_weight=0.8)],
        available_patrol_count=1,
        coverage_radius_meters=3000,
        shift=ShiftWindow(
            start=datetime(2026, 9, 4, 8, tzinfo=UTC),
            end=datetime(2026, 9, 4, 16, tzinfo=UTC),
        ),
    )
    marker = object()

    async def fake_get(_, __):
        return marker

    monkeypatch.setattr(prp_service, "get_optimization_run", fake_get)
    session = GenerationSession()
    result = asyncio.run(prp_service.generate_optimization(session, data))

    run = next(item for item in session.added if isinstance(item, OptimizationRun))
    stored = next(item for item in session.added if isinstance(item, PRPLocation))
    assert result is marker
    assert run.status == OptimizationRunStatus.COMPLETED
    assert run.parameters["result"]["covered_demand_ids"] == ["risk-1"]
    assert stored.status == PRPStatus.CANDIDATE
    assert stored.coverage_metadata["candidate_id"] == "safe-node-1"
    assert stored.coverage_metadata["assigned_demand_ids"] == ["risk-1"]
    assert float(stored.covered_risk) == 0.8
    assert session.commits == 2

