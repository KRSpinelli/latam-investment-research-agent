"""Tests for stub research report PDF generation."""

from __future__ import annotations

from latam_investment_research_agent.services.research_report_pdf import (
    generate_report_pdf,
    report_pdf_filename,
)


def test_generate_report_pdf_returns_valid_pdf_header() -> None:
    pdf_bytes = generate_report_pdf("coffee export revenues in Brazil")

    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")


def test_report_pdf_filename_slugifies_query() -> None:
    filename = report_pdf_filename("Coffee export revenues in Brazil?")

    assert filename.endswith(".pdf")
    assert " " not in filename
