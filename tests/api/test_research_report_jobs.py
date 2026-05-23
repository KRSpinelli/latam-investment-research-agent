"""API tests for async analyst report jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from latam_investment_research_agent.api.app import create_app
from latam_investment_research_agent.services.report_job_store import (
    ReportJobStatus,
    ReportJobStore,
)


@pytest.fixture
def report_job_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReportJobStore:
    """Provide an isolated job store for API tests."""
    store = ReportJobStore(base_directory=tmp_path)

    def _store() -> ReportJobStore:
        return store

    monkeypatch.setattr(
        "latam_investment_research_agent.services.report_job_store.get_report_job_store",
        _store,
    )
    monkeypatch.setattr(
        "latam_investment_research_agent.api.routes.research.get_report_job_store",
        _store,
    )
    return store


async def _immediate_report_job(job_id: str, request: object) -> None:
    """Complete a report job without running the full pipeline."""
    del request
    from latam_investment_research_agent.services.report_job_store import get_report_job_store

    store = get_report_job_store()
    record = store.get_job(job_id)
    if record is None:
        return
    pdf_path = record.job_directory / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    store.update_job(
        job_id,
        status=ReportJobStatus.COMPLETED,
        pdf_path=pdf_path,
        completed_at=datetime.now(tz=UTC),
        documents_ingested=1,
        clickhouse_rows=2,
        senso_chunks=3,
    )


def test_report_job_api_flow(
    report_job_store: ReportJobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST job, poll status, and download PDF."""
    monkeypatch.setattr(
        "latam_investment_research_agent.api.routes.research._execute_report_job",
        _immediate_report_job,
    )

    client = TestClient(create_app())
    create_response = client.post(
        "/api/v1/research/report/jobs",
        json={"query": "coffee export revenues in Brazil"},
    )
    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    status_response = client.get(f"/api/v1/research/report/jobs/{job_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "completed"
    assert body["clickhouse_rows"] == 2

    pdf_response = client.get(f"/api/v1/research/report/jobs/{job_id}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")


def test_report_job_not_found() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/research/report/jobs/does-not-exist")
    assert response.status_code == 404
