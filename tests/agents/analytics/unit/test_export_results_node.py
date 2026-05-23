"""Unit tests for the RAG export_results node."""

from __future__ import annotations

import pytest

from latam_investment_research_agent.agents.analytics.nodes.rag.export_results_node import (
    _prepare_export_dataframe,
)


def test_prepare_export_dataframe_puts_source_reference_first() -> None:
    """source_reference is always the first CSV column."""
    records = [{"year": 2025, "total_export_revenue": "100.00"}]
    dataframe = _prepare_export_dataframe(records)

    assert dataframe.columns[0] == "source_reference"
    assert dataframe["source_reference"].to_list() == [None]


def test_prepare_export_dataframe_preserves_existing_source_reference() -> None:
    """Existing source_reference values are kept and remain first."""
    records = [
        {
            "year": 2025,
            "source_reference": "https://example.com/report.pdf",
            "total_export_revenue": "100.00",
        }
    ]
    dataframe = _prepare_export_dataframe(records)

    assert dataframe.columns[0] == "source_reference"
    assert dataframe["source_reference"][0] == "https://example.com/report.pdf"
