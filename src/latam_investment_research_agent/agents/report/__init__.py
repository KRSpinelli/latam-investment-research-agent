"""Analyst report generation — narrative, charts, and PDF rendering."""

from latam_investment_research_agent.agents.report.models import (
    ChartArtifact,
    ReportContext,
    ReportNarrative,
)
from latam_investment_research_agent.agents.report.pdf_renderer import render_report_pdf

__all__ = [
    "ChartArtifact",
    "ReportContext",
    "ReportNarrative",
    "render_report_pdf",
]
