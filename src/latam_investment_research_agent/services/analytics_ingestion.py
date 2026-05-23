"""ClickHouse document ingestion for analytics (PDF and web sources)."""

from __future__ import annotations

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig
from latam_investment_research_agent.agents.analytics.graph.ingestion_graph import (
    build_ingestion_graph,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import (
    IngestionSummary,
)
from latam_investment_research_agent.agents.analytics.providers.clickhouse_provider import (
    managed_clickhouse_client,
)
from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument


def source_references_from_documents(documents: list[NimbleDocument]) -> list[str]:
    """Collect unique source URLs from successfully fetched Nimble documents.

    Args:
        documents: Documents returned by the research pipeline.

    Returns:
        De-duplicated final URLs (or original URLs) suitable for ingestion.
    """
    seen: set[str] = set()
    source_references: list[str] = []
    for document in documents:
        if not document.ok:
            continue
        source_reference = document.final_url or document.url
        if source_reference in seen:
            continue
        seen.add(source_reference)
        source_references.append(source_reference)
    return source_references


async def ingest_source_reference(source_reference: str) -> IngestionSummary:
    """Run the analytics ingestion graph for a single document URL.

    Args:
        source_reference: PDF or web page URL to fetch, extract, and persist.

    Returns:
        Structured ingestion summary from the LangGraph terminal node.
    """
    config = AnalyticsConfig()
    async with managed_clickhouse_client(config) as clickhouse_client:
        graph = build_ingestion_graph(config=config, clickhouse_client=clickhouse_client)
        result = await graph.ainvoke({"source_reference": source_reference})
    return result["ingestion_summary"]
