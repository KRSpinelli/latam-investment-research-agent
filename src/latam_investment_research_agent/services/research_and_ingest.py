"""Research pipeline followed by parallel analytics ingestion per document."""

from __future__ import annotations

import asyncio

from latam_investment_research_agent.agents.analytics.models.ingestion_state import (
    IngestionSummary,
)
from latam_investment_research_agent.schemas.research import (
    IngestionSummaryResponse,
    ResearchRequest,
    ResearchWithIngestionResponse,
)
from latam_investment_research_agent.services.analytics_ingestion import (
    ingest_source_reference,
    source_references_from_documents,
)
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline


def _ingestion_summary_to_response(summary: IngestionSummary) -> IngestionSummaryResponse:
    return IngestionSummaryResponse(
        source_reference=summary["source_reference"],
        total_datasets_found=summary["total_datasets_found"],
        datasets_succeeded=summary["datasets_succeeded"],
        datasets_failed=summary["datasets_failed"],
    )


async def run_research_and_ingest(
    request: ResearchRequest,
    pipeline: ResearchPipeline,
) -> ResearchWithIngestionResponse:
    """Run research, then ingest each successful document URL into ClickHouse in parallel.

    Args:
        request: Research query and optional seed URLs.
        pipeline: Configured Nimble → relevance → retrieval pipeline.

    Returns:
        Research results plus one ingestion summary per unique document URL.
    """
    research = pipeline.run(request)
    source_references = source_references_from_documents(research.documents)

    ingestion_summaries: list[IngestionSummaryResponse] = []
    if source_references:
        tasks = [
            asyncio.create_task(ingest_source_reference(source_reference))
            for source_reference in source_references
        ]
        summaries = await asyncio.gather(*tasks)
        ingestion_summaries = [
            _ingestion_summary_to_response(summary) for summary in summaries
        ]

    return ResearchWithIngestionResponse(
        research=research,
        ingestion_summaries=ingestion_summaries,
    )
