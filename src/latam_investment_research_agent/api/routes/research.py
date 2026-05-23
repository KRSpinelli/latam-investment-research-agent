from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from latam_investment_research_agent.api.deps import get_pipeline
from latam_investment_research_agent.api.schemas.research import (
    EXAMPLE_QUERIES,
    EXAMPLE_SEED_URLS,
    ExampleSeedsResponse,
    ResearchRequest,
    ResearchResponse,
    ResearchWithIngestionResponse,
)
from latam_investment_research_agent.services.research_and_ingest import run_research_and_ingest
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline
from latam_investment_research_agent.services.research_report_pdf import (
    generate_report_pdf,
    report_pdf_filename,
)

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


@router.get("/report/pdf")
def download_research_report_pdf(
    query: str = Query(
        ...,
        min_length=8,
        description="Research question to include on the report cover page.",
    ),
) -> Response:
    """Download a research report as PDF (stub).

    Returns a minimal valid PDF placeholder. Report generation will be
    implemented in a later iteration.
    """
    pdf_bytes = generate_report_pdf(query)
    filename = report_pdf_filename(query)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
