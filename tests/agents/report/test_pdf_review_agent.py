"""Tests for the PDF formatting review agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryOutput
from latam_investment_research_agent.agents.report.models import (
    ReportContext,
    ReportFormattingReview,
    ReportNarrative,
    ReportPdfLayoutHints,
)
from latam_investment_research_agent.agents.report.pdf_renderer import render_report_pdf
from latam_investment_research_agent.agents.report.pdf_review_agent import (
    extract_text_from_pdf,
    review_report_formatting,
)
from latam_investment_research_agent.agents.retrieval.schemas.routing import RetrievalOutcome
from latam_investment_research_agent.schemas.research import ResearchResponse, ResearchWithIngestionResponse


def _minimal_context(tmp_path: Path) -> ReportContext:
    research = ResearchResponse(
        task_id="task_test",
        query="coffee export revenues in Brazil",
        documents=[],
        signals=[],
        retrieval=RetrievalOutcome(
            signals_processed=0,
            signals_discarded=0,
            analysis_packet_id=None,
        ),
    )
    rag_output: RAGQueryOutput = {
        "export_file_path": None,
        "rationale": "Sample.",
        "sql_queries_used": ["SELECT 1"],
        "row_count": 5,
        "was_truncated": False,
    }
    return ReportContext(
        query=research.query,
        job_directory=tmp_path,
        ingestion=ResearchWithIngestionResponse(research=research),
        rag_output=rag_output,
        query_result_records=[{"year": 2024, "bags": 100}],
        narrative=ReportNarrative(
            executive_summary="Draft summary with  no double spaces.",
            key_findings=["Finding one"],
            quantitative_analysis="Some numbers here.",
            qualitative_analysis="Qualitative text.",
            limitations="Limits.",
            methodology="Method.",
        ),
    )


def test_extract_text_from_pdf_reads_rendered_document(tmp_path: Path) -> None:
    pdf_bytes = render_report_pdf(_minimal_context(tmp_path))
    extracted = extract_text_from_pdf(pdf_bytes)
    assert "coffee export" in extracted.lower() or "Executive" in extracted


@pytest.mark.asyncio
async def test_review_report_formatting_returns_cleaned_narrative(tmp_path: Path) -> None:
    context = _minimal_context(tmp_path)
    draft_pdf = render_report_pdf(context)

    cleaned = ReportFormattingReview(
        narrative=ReportNarrative(
            executive_summary="Polished executive summary.",
            key_findings=["Polished finding"],
            quantitative_analysis="Polished quantitative section.",
            qualitative_analysis="Polished qualitative section.",
            limitations="Polished limitations.",
            methodology="Polished methodology.",
        ),
        layout_hints=ReportPdfLayoutHints(
            page_break_before_charts=True,
            chart_display_order=["line", "bar", "pie"],
        ),
        formatting_changes_summary="Tightened prose and added page breaks.",
    )

    structured_mock = MagicMock()
    structured_mock.ainvoke = AsyncMock(return_value=cleaned)
    language_model = MagicMock()
    language_model.with_structured_output = MagicMock(return_value=structured_mock)

    review = await review_report_formatting(context, draft_pdf, language_model)

    assert review.narrative.executive_summary.startswith("Polished")
    assert review.layout_hints.page_break_before_charts is True
