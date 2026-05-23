"""Tests for report PDF rendering."""

from __future__ import annotations

from pathlib import Path

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryOutput
from latam_investment_research_agent.agents.report.models import ReportContext, ReportNarrative
from latam_investment_research_agent.agents.report.pdf_renderer import render_report_pdf
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
        "rationale": "Sample rationale.",
        "sql_queries_used": ["SELECT year, revenue FROM exports"],
        "row_count": 2,
        "was_truncated": False,
    }
    return ReportContext(
        query=research.query,
        job_directory=tmp_path,
        ingestion=ResearchWithIngestionResponse(research=research),
        rag_output=rag_output,
        query_result_records=[
            {"year": 2023, "revenue": 100},
            {"year": 2024, "revenue": 120},
        ],
        narrative=ReportNarrative(
            executive_summary="Exports grew year over year.",
            key_findings=["Revenue increased."],
            quantitative_analysis="Quantitative section.",
            qualitative_analysis="Qualitative section.",
            limitations="Stub data only.",
            methodology="Automated pipeline.",
        ),
    )


def test_render_report_pdf_returns_valid_pdf(tmp_path: Path) -> None:
    pdf_bytes = render_report_pdf(_minimal_context(tmp_path))

    assert pdf_bytes.startswith(b"%PDF")
