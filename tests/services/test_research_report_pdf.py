"""Tests for report PDF filename helpers."""

from __future__ import annotations

from latam_investment_research_agent.services.research_report_pdf import report_pdf_filename


def test_report_pdf_filename_slugifies_query() -> None:
    filename = report_pdf_filename("Coffee export revenues in Brazil?")

    assert filename.endswith(".pdf")
    assert " " not in filename
