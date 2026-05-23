from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response

from latam_investment_research_agent.api.deps import get_pipeline
from latam_investment_research_agent.api.schemas.research import (
    EXAMPLE_QUERIES,
    EXAMPLE_SEED_URLS,
    ExampleSeedsResponse,
    ReportJobCreateResponse,
    ReportJobStatusResponse,
    ResearchRequest,
    ResearchResponse,
    ResearchWithIngestionResponse,
)
from latam_investment_research_agent.services.report_job_store import (
    ReportJobRecord,
    ReportJobStatus,
    get_report_job_store,
)
from latam_investment_research_agent.services.research_and_ingest import run_research_and_ingest
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline
from latam_investment_research_agent.services.research_report_orchestrator import (
    run_report_pipeline,
)
from latam_investment_research_agent.services.research_report_pdf import report_pdf_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.get("/examples", response_model=ExampleSeedsResponse)
def research_examples() -> ExampleSeedsResponse:
    """Demo queries and seed URLs for the frontend."""
    return ExampleSeedsResponse(queries=EXAMPLE_QUERIES, seed_urls=EXAMPLE_SEED_URLS)


@router.post("", response_model=ResearchResponse)
def run_research(
    body: ResearchRequest,
    pipeline: ResearchPipeline = Depends(get_pipeline),
) -> ResearchResponse:
    """
    Run the full research pipeline:

    Nimble (search + scrape) → relevance filter → retrieval (ClickHouse / Senso / analysis).
    """
    return pipeline.run(body)


@router.post("/ingest", response_model=ResearchWithIngestionResponse)
async def run_research_and_ingest_endpoint(
    body: ResearchRequest,
    pipeline: ResearchPipeline = Depends(get_pipeline),
) -> ResearchWithIngestionResponse:
    """
    Run the research pipeline, then ingest each returned document into ClickHouse
    and the Senso knowledge base.

    Both backends ingest concurrently — one async task per unique source URL, with
    ClickHouse and Senso work running in parallel.
    """
    return await run_research_and_ingest(body, pipeline)


async def _execute_report_job(job_id: str, request: ResearchRequest) -> None:
    """Background worker that runs the report pipeline and updates job status.

    Args:
        job_id: Report job identifier.
        request: Research request for the pipeline.
    """
    store = get_report_job_store()
    record = store.get_job(job_id)
    if record is None:
        return

    pipeline = get_pipeline()
    store.update_job(job_id, status=ReportJobStatus.RUNNING)

    try:
        context, pdf_bytes = await run_report_pipeline(
            request,
            pipeline,
            job_directory=record.job_directory,
        )
        pdf_path = record.job_directory / "report.pdf"
        pdf_path.write_bytes(pdf_bytes)
        store.update_job(
            job_id,
            status=ReportJobStatus.COMPLETED,
            pdf_path=pdf_path,
            completed_at=datetime.now(tz=UTC),
            documents_ingested=len(context.ingestion.research.documents),
            clickhouse_rows=context.rag_output.get("row_count", 0),
            senso_chunks=len(context.senso_chunks),
        )
    except Exception as error:
        logger.exception("Report job %s failed", job_id)
        store.update_job(
            job_id,
            status=ReportJobStatus.FAILED,
            error=str(error),
        )


@router.post(
    "/report/jobs",
    response_model=ReportJobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_report_job(
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
) -> ReportJobCreateResponse:
    """Start async analyst report generation (research, ingestion, RAG, PDF).

    Poll ``GET /report/jobs/{job_id}`` until ``status`` is ``completed``, then
    download the PDF from ``GET /report/jobs/{job_id}/pdf``.
    """
    store = get_report_job_store()
    record = store.create_job(body.query)
    background_tasks.add_task(_execute_report_job, record.job_id, body)
    return ReportJobCreateResponse(
        job_id=record.job_id,
        status=record.status.value,
        query=record.query,
    )


def _job_status_response(job: ReportJobRecord) -> ReportJobStatusResponse:
    """Map a store record to an API response.

    Args:
        job: Report job record from the job store.

    Returns:
        API status payload.
    """
    return ReportJobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        query=job.query,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        documents_ingested=job.documents_ingested,
        clickhouse_rows=job.clickhouse_rows,
        senso_chunks=job.senso_chunks,
    )


@router.get("/report/jobs/{job_id}", response_model=ReportJobStatusResponse)
def get_report_job_status(job_id: str) -> ReportJobStatusResponse:
    """Poll report job status."""
    record = get_report_job_store().get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Report job {job_id!r} not found")
    return _job_status_response(record)


@router.get("/report/jobs/{job_id}/pdf")
def download_report_job_pdf(job_id: str) -> Response:
    """Download the generated PDF when the job has completed."""
    record = get_report_job_store().get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Report job {job_id!r} not found")
    if record.status != ReportJobStatus.COMPLETED or record.pdf_path is None:
        raise HTTPException(
            status_code=409,
            detail=f"Report job is not ready (status={record.status.value})",
        )
    if not record.pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Report PDF file is missing on disk")

    filename = report_pdf_filename(record.query)
    return FileResponse(
        path=record.pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
