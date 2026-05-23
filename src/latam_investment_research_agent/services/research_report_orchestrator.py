"""Orchestrate research, ingestion, RAG, Senso, and PDF report generation."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig
from latam_investment_research_agent.agents.analytics.graph.rag_query_graph import (
    build_rag_query_graph,
)
from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryOutput
from latam_investment_research_agent.agents.analytics.providers.clickhouse_provider import (
    managed_clickhouse_client,
)
from latam_investment_research_agent.agents.analytics.providers.llm_provider import (
    create_llm_provider,
)
from latam_investment_research_agent.agents.report.chart_builder import (
    build_charts_from_records,
)
from latam_investment_research_agent.agents.report.models import ReportContext
from latam_investment_research_agent.agents.report.narrative_agent import (
    generate_report_narrative,
)
from latam_investment_research_agent.agents.report.pdf_renderer import render_report_pdf
from latam_investment_research_agent.agents.report.pdf_review_agent import (
    review_report_formatting,
)
from latam_investment_research_agent.agents.semantic_storage.search import search_memory
from latam_investment_research_agent.schemas.research import ResearchRequest, ResearchWithIngestionResponse
from latam_investment_research_agent.services.report_quantitative_fallback import (
    ensure_quantitative_data,
)
from latam_investment_research_agent.services.research_and_ingest import run_research_and_ingest
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline

logger = logging.getLogger(__name__)

_EMPTY_RAG_OUTPUT: RAGQueryOutput = {
    "export_file_path": None,
    "rationale": "RAG query was not executed.",
    "sql_queries_used": [],
    "row_count": 0,
    "was_truncated": False,
}


async def _search_senso_for_report(
    query: str,
    ingestion: ResearchWithIngestionResponse,
) -> list[Any]:
    """Run Senso memory search for report qualitative context.

    Args:
        query: Research question.
        ingestion: Research plus ingestion outcomes (for scoped content IDs).

    Returns:
        Senso search chunks, or an empty list on failure.
    """
    senso_content_ids = [
        result.kb_node_id
        for result in ingestion.senso_ingestion_results
        if result.kb_node_id and not result.error
    ]
    logger.info("Report pipeline: Senso search (%d scoped ids)", len(senso_content_ids))
    try:
        senso_chunks = await search_memory(
            query,
            max_results=12,
            content_ids=senso_content_ids or None,
        )
        if not senso_chunks and senso_content_ids:
            logger.info("Scoped Senso search returned no chunks; retrying org-wide")
            senso_chunks = await search_memory(query, max_results=12)
        return senso_chunks
    except Exception as error:
        logger.warning("Senso search failed: %s", error)
        return []


async def _run_clickhouse_rag_phase(
    request: ResearchRequest,
    ingestion: ResearchWithIngestionResponse,
    job_directory: Path,
    analytics_config: AnalyticsConfig,
) -> tuple[RAGQueryOutput, list[dict[str, Any]]]:
    """Run the RAG graph and quantitative fallback against ClickHouse.

    Args:
        request: Research request.
        ingestion: Ingestion outcomes from this session.
        job_directory: Job export directory.
        analytics_config: Analytics configuration.

    Returns:
        Tuple of RAG output metadata and merged quantitative rows.
    """
    rag_output: RAGQueryOutput = dict(_EMPTY_RAG_OUTPUT)
    query_result_records: list[dict[str, Any]] = []

    async with managed_clickhouse_client(analytics_config) as clickhouse_client:
        logger.info("Report pipeline: ClickHouse RAG query")
        rag_graph = build_rag_query_graph(
            config=analytics_config,
            clickhouse_client=clickhouse_client,
        )
        rag_question = (
            f"{request.query}\n\n"
            "ClickHouse query budget: unlimited — run many diverse SELECT queries across "
            "all relevant tables (trends, totals, rankings, segment breakdowns).\n"
            "Use only columns that exist in the selected ClickHouse table schemas. "
            "Prefer broad SELECT queries without geographic or price filters unless "
            "those columns are explicitly present."
        )
        rag_state = await rag_graph.ainvoke(
            {
                "natural_language_question": rag_question,
                "export_row_limit": 10_000,
                "export_directory": str(job_directory),
            }
        )
        rag_output = dict(rag_state.get("rag_query_output", _EMPTY_RAG_OUTPUT))
        query_result_records = list(rag_state.get("query_result_records", []))

        logger.info("Report pipeline: ensuring minimum ClickHouse quantitative rows")
        quantitative_bundle = await ensure_quantitative_data(
            request.query,
            ingestion.ingestion_summaries,
            clickhouse_client,
            existing_rows=query_result_records,
            existing_sql_queries=list(rag_output.get("sql_queries_used", [])),
            max_concurrent_snapshots=analytics_config.clickhouse_max_concurrent_queries,
        )
        query_result_records = quantitative_bundle.rows
        rag_output["row_count"] = len(query_result_records)
        rag_output["sql_queries_used"] = quantitative_bundle.sql_queries
        if quantitative_bundle.data_source_note:
            rag_output["rationale"] = (
                f"{rag_output.get('rationale', '')} "
                f"{quantitative_bundle.data_source_note}"
            ).strip()

    return rag_output, query_result_records


async def run_report_pipeline(
    request: ResearchRequest,
    pipeline: ResearchPipeline,
    *,
    job_directory: Path,
) -> tuple[ReportContext, bytes]:
    """Run the full analyst report pipeline and return context plus PDF bytes.

    Args:
        request: Research query and optional seed URLs.
        pipeline: Configured research pipeline.
        job_directory: Writable directory for exports, charts, and the PDF.

    Returns:
        Tuple of report context and rendered PDF bytes.
    """
    job_directory.mkdir(parents=True, exist_ok=True)

    logger.info("Report pipeline: research and ingestion")
    ingestion = await run_research_and_ingest(request, pipeline)

    analytics_config = AnalyticsConfig()
    logger.info("Report pipeline: ClickHouse RAG + Senso search (parallel)")
    (rag_output, query_result_records), senso_chunks = await asyncio.gather(
        _run_clickhouse_rag_phase(request, ingestion, job_directory, analytics_config),
        _search_senso_for_report(request.query, ingestion),
    )

    context = ReportContext(
        query=request.query,
        job_directory=job_directory,
        ingestion=ingestion,
        rag_output=rag_output,
        query_result_records=query_result_records,
        senso_chunks=senso_chunks,
    )

    logger.info("Report pipeline: building charts")
    context.charts = build_charts_from_records(
        query_result_records,
        query=request.query,
        output_directory=job_directory / "charts",
    )

    logger.info("Report pipeline: generating narrative")
    language_model = create_llm_provider(analytics_config)
    context.narrative = await generate_report_narrative(context, language_model)

    logger.info("Report pipeline: rendering draft PDF")
    draft_pdf_bytes = render_report_pdf(context)
    draft_path = job_directory / "report_draft.pdf"
    draft_path.write_bytes(draft_pdf_bytes)

    logger.info("Report pipeline: PDF formatting review agent")
    formatting_review = await review_report_formatting(
        context,
        draft_pdf_bytes,
        language_model,
    )
    context.narrative = formatting_review.narrative
    context.layout_hints = formatting_review.layout_hints

    logger.info("Report pipeline: rendering final PDF")
    pdf_bytes = render_report_pdf(context)
    pdf_path = job_directory / "report.pdf"
    pdf_path.write_bytes(pdf_bytes)

    return context, pdf_bytes
