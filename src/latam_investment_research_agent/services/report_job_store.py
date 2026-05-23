"""In-memory store for async analyst report generation jobs.

MVP limitation: jobs live in process memory and on local disk under
``exports/report_jobs``. Use a single uvicorn worker for development.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class ReportJobStatus(str, Enum):
    """Lifecycle status for a report generation job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportJobRecord:
    """Stored state for one report job."""

    job_id: str
    query: str
    status: ReportJobStatus
    job_directory: Path
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    completed_at: datetime | None = None
    error: str | None = None
    pdf_path: Path | None = None
    documents_ingested: int = 0
    clickhouse_rows: int = 0
    senso_chunks: int = 0


class ReportJobStore:
    """Thread-safe in-memory registry of report jobs."""

    def __init__(self, base_directory: Path | None = None) -> None:
        self._base_directory = base_directory or Path("exports/report_jobs")
        self._jobs: dict[str, ReportJobRecord] = {}
        self._lock = threading.Lock()

    def create_job(self, query: str) -> ReportJobRecord:
        """Create a pending job and its working directory.

        Args:
            query: Research question for the report.

        Returns:
            New job record.
        """
        job_id = f"report_{uuid.uuid4().hex[:12]}"
        job_directory = self._base_directory / job_id
        job_directory.mkdir(parents=True, exist_ok=True)
        record = ReportJobRecord(
            job_id=job_id,
            query=query,
            status=ReportJobStatus.PENDING,
            job_directory=job_directory,
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> ReportJobRecord | None:
        """Return a job record by identifier.

        Args:
            job_id: Job identifier.

        Returns:
            Job record or None if not found.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **fields: object) -> ReportJobRecord | None:
        """Update fields on a job record.

        Args:
            job_id: Job identifier.
            **fields: Attributes to set on the record.

        Returns:
            Updated record or None if not found.
        """
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            for key, value in fields.items():
                setattr(record, key, value)
            record.updated_at = datetime.now(tz=UTC)
            return record


_default_store: ReportJobStore | None = None
_store_lock = threading.Lock()


def get_report_job_store() -> ReportJobStore:
    """Return the process-wide report job store singleton.

    Returns:
        Shared ReportJobStore instance.
    """
    global _default_store
    with _store_lock:
        if _default_store is None:
            _default_store = ReportJobStore()
        return _default_store
