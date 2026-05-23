"""Tests for the in-memory report job store."""

from __future__ import annotations

from latam_investment_research_agent.services.report_job_store import (
    ReportJobStatus,
    ReportJobStore,
)


def test_report_job_store_lifecycle(tmp_path) -> None:
    store = ReportJobStore(base_directory=tmp_path)
    record = store.create_job("coffee export revenues in Brazil")

    assert record.status == ReportJobStatus.PENDING
    assert record.job_directory.is_dir()

    updated = store.update_job(
        record.job_id,
        status=ReportJobStatus.RUNNING,
    )
    assert updated is not None
    assert updated.status == ReportJobStatus.RUNNING

    completed = store.update_job(
        record.job_id,
        status=ReportJobStatus.COMPLETED,
        clickhouse_rows=5,
    )
    assert completed is not None
    assert completed.clickhouse_rows == 5
