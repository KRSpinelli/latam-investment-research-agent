"""Build matplotlib charts from ClickHouse RAG query rows."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

from latam_investment_research_agent.agents.report.models import ChartArtifact

logger = logging.getLogger(__name__)

_MAX_CHARTS = 2
_YEAR_COLUMN_PATTERN = re.compile(r"year|period|date|fiscal|ano|safra", re.IGNORECASE)


def _is_numeric_column(series: pl.Series) -> bool:
    """Return True when a Polars series holds numeric values.

    Args:
        series: Column to inspect.

    Returns:
        True if the column dtype is numeric.
    """
    return series.dtype in (
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
        pl.Float32,
        pl.Float64,
        pl.Decimal,
    )


def _pick_category_column(frame: pl.DataFrame) -> str | None:
    """Pick a label column for chart x-axis.

    Args:
        frame: Query result data.

    Returns:
        Column name or None when no suitable column exists.
    """
    for column_name in frame.columns:
        if _YEAR_COLUMN_PATTERN.search(column_name):
            return column_name
    for column_name in frame.columns:
        if column_name in {"source_reference", "content_hash", "ingestion_timestamp"}:
            continue
        if not _is_numeric_column(frame[column_name]):
            return column_name
    return None


def _pick_value_column(frame: pl.DataFrame, category_column: str | None) -> str | None:
    """Pick the first numeric column suitable for plotting.

    Args:
        frame: Query result data.
        category_column: Column used on the x-axis, if any.

    Returns:
        Numeric column name or None.
    """
    for column_name in frame.columns:
        if column_name == category_column:
            continue
        if _is_numeric_column(frame[column_name]):
            return column_name
    return None


def _save_chart(
    *,
    output_path: Path,
    title: str,
    categories: list[str],
    values: list[float],
    chart_type: str,
) -> None:
    """Write one chart image to disk.

    Args:
        output_path: Destination PNG path.
        title: Chart title.
        categories: X-axis labels.
        values: Y-axis values.
        chart_type: ``line`` or ``bar``.
    """
    figure, axis = plt.subplots(figsize=(8, 4.5))
    try:
        if chart_type == "line":
            axis.plot(range(len(values)), values, marker="o", linewidth=2, color="#1f4e79")
            axis.set_xticks(range(len(categories)))
            axis.set_xticklabels(categories, rotation=45, ha="right")
        else:
            axis.bar(categories, values, color="#2e6da4")
            axis.tick_params(axis="x", rotation=45)
        axis.set_title(title, fontsize=12, fontweight="bold")
        axis.grid(True, linestyle="--", alpha=0.35)
        axis.set_ylabel("Value")
        figure.tight_layout()
        figure.savefig(output_path, dpi=150, bbox_inches="tight")
    finally:
        plt.close(figure)


def build_charts_from_records(
    records: list[dict[str, Any]],
    *,
    query: str,
    output_directory: Path,
) -> list[ChartArtifact]:
    """Build up to two charts from RAG query result rows.

    Args:
        records: Rows returned by the ClickHouse RAG graph.
        query: Original research question (used in chart titles).
        output_directory: Directory where PNG files are written.

    Returns:
        Chart metadata for PDF embedding.
    """
    if not records:
        return []

    frame = pl.DataFrame(records)
    if frame.is_empty():
        return []

    category_column = _pick_category_column(frame)
    value_column = _pick_value_column(frame, category_column)
    if value_column is None:
        logger.info("No numeric columns found for chart generation")
        return []

    if category_column is None:
        category_column = "index"
        frame = frame.with_row_index(name=category_column)

    plot_frame = frame.select([category_column, value_column]).drop_nulls().head(24)
    if plot_frame.is_empty():
        return []

    categories = [str(value) for value in plot_frame[category_column].to_list()]
    numeric_values = plot_frame[value_column].cast(pl.Float64, strict=False).to_list()
    values = [float(value) if value is not None else 0.0 for value in numeric_values]

    chart_type = "line" if _YEAR_COLUMN_PATTERN.search(category_column) else "bar"
    title_suffix = query[:60] + ("…" if len(query) > 60 else "")
    chart_title = f"{value_column.replace('_', ' ').title()} — {title_suffix}"

    output_directory.mkdir(parents=True, exist_ok=True)
    chart_path = output_directory / f"chart_{value_column}.png"
    _save_chart(
        output_path=chart_path,
        title=chart_title,
        categories=categories,
        values=values,
        chart_type=chart_type,
    )

    artifacts = [
        ChartArtifact(
            title=chart_title,
            file_path=chart_path,
            chart_type=chart_type,
        )
    ]

    if len(frame.columns) < 3 or _MAX_CHARTS < 2:
        return artifacts

    remaining_numeric = [
        column_name
        for column_name in frame.columns
        if column_name not in {category_column, value_column}
        and _is_numeric_column(frame[column_name])
    ]
    if not remaining_numeric:
        return artifacts

    second_value_column = remaining_numeric[0]
    second_frame = frame.select([category_column, second_value_column]).drop_nulls().head(24)
    if second_frame.is_empty():
        return artifacts

    second_categories = [str(value) for value in second_frame[category_column].to_list()]
    second_numeric = second_frame[second_value_column].cast(pl.Float64, strict=False).to_list()
    second_values = [float(value) if value is not None else 0.0 for value in second_numeric]
    second_chart_type = (
        "line" if _YEAR_COLUMN_PATTERN.search(category_column) else "bar"
    )
    second_title = f"{second_value_column.replace('_', ' ').title()} — {title_suffix}"
    second_path = output_directory / f"chart_{second_value_column}.png"
    _save_chart(
        output_path=second_path,
        title=second_title,
        categories=second_categories,
        values=second_values,
        chart_type=second_chart_type,
    )
    artifacts.append(
        ChartArtifact(
            title=second_title,
            file_path=second_path,
            chart_type=second_chart_type,
        )
    )
    return artifacts
