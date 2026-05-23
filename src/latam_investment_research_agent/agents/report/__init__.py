"""Analyst report generation — narrative, charts, and PDF rendering."""

from latam_investment_research_agent.agents.report.models import (
    ChartArtifact,
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

__all__ = [
    "ChartArtifact",
    "ReportContext",
    "ReportFormattingReview",
    "ReportNarrative",
    "ReportPdfLayoutHints",
    "extract_text_from_pdf",
    "render_report_pdf",
    "review_report_formatting",
]
