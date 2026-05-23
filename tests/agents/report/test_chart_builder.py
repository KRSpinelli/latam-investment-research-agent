"""Tests for report chart generation."""

from __future__ import annotations

from pathlib import Path

from latam_investment_research_agent.agents.report.chart_builder import (
    build_charts_from_records,
)


def test_build_charts_from_records_creates_png(tmp_path: Path) -> None:
    records = [
        {"year": 2022, "export_revenue": 1000.0},
        {"year": 2023, "export_revenue": 1200.0},
        {"year": 2024, "export_revenue": 1500.0},
    ]

    charts = build_charts_from_records(
        records,
        query="coffee export revenues by year",
        output_directory=tmp_path,
    )

    assert len(charts) >= 1
    assert charts[0].file_path.is_file()
    assert charts[0].file_path.suffix == ".png"


def test_build_charts_from_empty_records_returns_empty(tmp_path: Path) -> None:
    charts = build_charts_from_records(
        [],
        query="no data",
        output_directory=tmp_path,
    )

    assert charts == []
