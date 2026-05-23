from fastapi import APIRouter, Depends

from latam_investment_research_agent.api.deps import get_pipeline
from latam_investment_research_agent.api.schemas.research import (
    EXAMPLE_QUERIES,
    EXAMPLE_SEED_URLS,
    ExampleSeedsResponse,
    ResearchRequest,
    ResearchResponse,
)
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline

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
