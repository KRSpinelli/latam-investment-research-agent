"""Research pipeline followed by parallel analytics ingestion per document."""

from __future__ import annotations

import asyncio
import logging

from latam_investment_research_agent.agents.analytics.models.domain import (
    DatasetIngestionFailure,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import (
    IngestionSummary,
)
from latam_investment_research_agent.schemas.research import (
    IngestionSummaryResponse,
    ResearchRequest,
    ResearchWithIngestionResponse,
)

logger = logging.getLogger(__name__)
from latam_investment_research_agent.services.analytics_ingestion import (
    ingest_source_reference,
    source_references_from_documents,
)
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline
from latam_investment_research_agent.services.semantic_storage_ingestion import (
    ingest_sources_to_senso,
)


def _ingestion_summary_to_response(summary: IngestionSummary) -> IngestionSummaryResponse:
    return IngestionSummaryResponse(
        source_reference=summary["source_reference"],
        total_datasets_found=summary["total_datasets_found"],
        datasets_succeeded=summary["datasets_succeeded"],
        datasets_failed=summary["datasets_failed"],
    )


async def _ingest_clickhouse_source_safe(
    source_reference: str,
) -> IngestionSummaryResponse:
    """Run ClickHouse ingestion for one URL, returning a failure summary on error.

    Args:
        source_reference: Document URL to ingest.

    Returns:
        Ingestion summary for the URL (success or captured exception).
    """
    try:
        summary = await ingest_source_reference(source_reference)
        return _ingestion_summary_to_response(summary)
    except Exception as error:
        logger.exception("ClickHouse ingestion failed for %s", source_reference)
        return IngestionSummaryResponse(
            source_reference=source_reference,
            total_datasets_found=0,
            datasets_succeeded=[],
            datasets_failed=[
                DatasetIngestionFailure(
                    dataset_name="ingestion",
                    error_detail=str(error),
                )
            ],
        )


async def run_research_and_ingest(
    request: ResearchRequest,
    pipeline: ResearchPipeline,
) -> ResearchWithIngestionResponse:
    """Run research, then ingest each document URL into ClickHouse and Senso in parallel.

    ClickHouse numeric ingestion and Senso semantic ingestion run concurrently
    (each backend uses ``asyncio.gather`` over one task per source URL).

    Args:
        request: Research query and optional seed URLs.
        pipeline: Configured Nimble → relevance → retrieval pipeline.

    Returns:
        Research results plus per-URL ClickHouse and Senso ingestion outcomes.
    """
    research = pipeline.run(request)
    source_references = source_references_from_documents(research.documents)

    ingestion_summaries: list[IngestionSummaryResponse] = []
    senso_ingestion_results = []

    if source_references:
        clickhouse_tasks = [
            asyncio.create_task(_ingest_clickhouse_source_safe(source_reference))
            for source_reference in source_references
        ]
        senso_task = asyncio.create_task(
            ingest_sources_to_senso(source_references, research)
        )
        ingestion_summaries, senso_ingestion_results = await asyncio.gather(
            asyncio.gather(*clickhouse_tasks),
            senso_task,
        )

    return ResearchWithIngestionResponse(
        research=research,
        ingestion_summaries=ingestion_summaries,
        senso_ingestion_results=senso_ingestion_results,
    )
