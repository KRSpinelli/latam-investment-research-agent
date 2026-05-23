"""LLM narrative generation for analyst PDF reports."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from latam_investment_research_agent.agents.report.models import ReportContext, ReportNarrative

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior LatAm investment research analyst writing an institutional
research report. Use only the evidence provided. Be precise, neutral, and concise.
Highlight Brazil / Latin America context when relevant.

Quantitative rules:
- If sample quantitative rows are provided (row count > 0), you MUST cite specific
  numbers from those rows in quantitative_analysis and key_findings.
- Never write that "no quantitative data" or "row count = 0" when rows are present.
- When rows describe market aggregates rather than named companies, frame them as
  market context and macro backdrop, then connect qualitatively to the research question.
- Always produce a coherent story from the evidence available."""


def _format_rows_sample(records: list[dict[str, Any]], limit: int = 15) -> str:
    """Serialize a sample of query rows for the LLM prompt.

    Args:
        records: ClickHouse query result rows.
        limit: Maximum rows to include.

    Returns:
        JSON string or a no-data message.
    """
    if not records:
        return (
            "No ClickHouse rows were available after all fallback strategies. "
            "Rely on Senso excerpts and research signals only."
        )
    sample = records[:limit]
    table_names = sorted({str(row.get("_snapshot_table", "")) for row in sample if row.get("_snapshot_table")})
    header = f"{len(records)} total row(s)"
    if table_names:
        header += f" from table(s): {', '.join(table_names)}"
    return f"{header}\n{json.dumps(sample, indent=2, default=str)}"


def _format_senso_chunks(context: ReportContext) -> str:
    """Format Senso chunks for the LLM prompt.

    Args:
        context: Report pipeline context.

    Returns:
        Plain-text excerpt block.
    """
    if not context.senso_chunks:
        return "No Senso knowledge-base excerpts available."
    parts: list[str] = []
    for chunk in context.senso_chunks[:8]:
        parts.append(f"[{chunk.title} | score={chunk.score:.2f}]\n{chunk.content[:800]}")
    return "\n\n---\n\n".join(parts)


def _format_ingestion_summary(context: ReportContext) -> str:
    """Summarize research and ingestion outcomes.

    Args:
        context: Report pipeline context.

    Returns:
        Plain-text summary for the LLM.
    """
    research = context.ingestion.research
    lines = [
        f"Documents fetched: {len(research.documents)}",
        f"Signals classified: {len(research.signals)}",
        f"ClickHouse ingestions: {len(context.ingestion.ingestion_summaries)}",
        f"Senso ingestions: {len(context.ingestion.senso_ingestion_results)}",
    ]
    for summary in context.ingestion.ingestion_summaries:
        lines.append(
            f"  - {summary.source_reference}: "
            f"{len(summary.datasets_succeeded)} datasets ok, "
            f"{len(summary.datasets_failed)} failed"
        )
    for senso_result in context.ingestion.senso_ingestion_results:
        status = "ok" if not senso_result.error else f"error: {senso_result.error}"
        lines.append(f"  - Senso {senso_result.source_reference}: {status}")
    return "\n".join(lines)


def _build_user_prompt(context: ReportContext) -> str:
    """Compose the user message for narrative generation.

    Args:
        context: Report pipeline context.

    Returns:
        Prompt text for the LLM.
    """
    rag = context.rag_output
    sql_block = "\n".join(rag.get("sql_queries_used", [])) or "None"
    return f"""Write an investment research report for this question:

Question: {context.query}

ClickHouse RAG rationale:
{rag.get("rationale", "")}

SQL executed:
{sql_block}

Row count: {rag.get("row_count", 0)}
Truncated: {rag.get("was_truncated", False)}

IMPORTANT: The row count above is authoritative. If row count > 0, you must analyze
the sample rows below with specific numbers — do not claim quantitative data is missing.

Sample quantitative rows:
{_format_rows_sample(context.query_result_records)}

Senso qualitative excerpts:
{_format_senso_chunks(context)}

Research and ingestion summary:
{_format_ingestion_summary(context)}
"""


async def generate_report_narrative(
    context: ReportContext,
    language_model: BaseChatModel,
) -> ReportNarrative:
    """Generate structured report narrative from pipeline artifacts.

    Args:
        context: Collected research, RAG, and Senso artifacts.
        language_model: LangChain chat model with structured output support.

    Returns:
        Structured narrative sections for PDF rendering.
    """
    structured_language_model = language_model.with_structured_output(ReportNarrative)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_build_user_prompt(context)),
    ]
    logger.info("Generating report narrative via LLM")
    result = await structured_language_model.ainvoke(messages)
    if isinstance(result, ReportNarrative):
        return result
    return ReportNarrative.model_validate(result)
