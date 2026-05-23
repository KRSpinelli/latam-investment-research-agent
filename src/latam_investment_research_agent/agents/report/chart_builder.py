"""Build matplotlib charts from ClickHouse query rows."""

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

_YEAR_COLUMN_PATTERN = re.compile(r"year|period|date|fiscal|ano|safra|month|quarter", re.IGNORECASE)
_MINIMUM_CHART_POINTS = 3
_PIE_SLICE_LIMIT = 8
_PLOT_POINT_LIMIT = 24
_REQUIRED_CHART_TYPES = ("line", "bar", "pie")


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
    """Pick a label column for chart axes.

    Args:
        frame: Query result data.

    Returns:
        Column name or None when no suitable column exists.
    """
    for column_name in frame.columns:
        if _YEAR_COLUMN_PATTERN.search(column_name):
            return column_name
    for column_name in frame.columns:
        if column_name in {
            "source_reference",
            "content_hash",
            "ingestion_timestamp",
            "_snapshot_table",
        }:
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
        if column_name in {"content_hash", "ingestion_timestamp", "_snapshot_table"}:
            continue
        if _is_numeric_column(frame[column_name]):
            return column_name
    return None


def _prepare_plot_series(
    categories: list[str],
    values: list[float],
    *,
    limit: int = _PLOT_POINT_LIMIT,
) -> tuple[list[str], list[float]]:
    """Trim and sort plot data for readability.

    Args:
        categories: Category labels.
        values: Numeric values aligned with categories.
        limit: Maximum points to plot.

    Returns:
        Trimmed categories and values sorted by value descending.
    """
    pairs = [
        (label, value)
        for label, value in zip(categories, values, strict=True)
        if value is not None
    ]
    pairs = [(label, float(value)) for label, value in pairs if value == value]
    pairs.sort(key=lambda item: item[1], reverse=True)
    pairs = pairs[:limit]
    if not pairs:
        return [], []
    return [label for label, _ in pairs], [value for _, value in pairs]


def _prepare_pie_series(
    categories: list[str],
    values: list[float],
) -> tuple[list[str], list[float]]:
    """Collapse long tails into an "Other" slice for pie charts.

    Args:
        categories: Category labels.
        values: Numeric values.

    Returns:
        At most ``_PIE_SLICE_LIMIT`` slices plus optional "Other".
    """
    trimmed_categories, trimmed_values = _prepare_plot_series(categories, values)
    if len(trimmed_categories) <= _PIE_SLICE_LIMIT:
        return trimmed_categories, trimmed_values

    top_categories = trimmed_categories[: _PIE_SLICE_LIMIT - 1]
    top_values = trimmed_values[: _PIE_SLICE_LIMIT - 1]
    other_total = sum(trimmed_values[_PIE_SLICE_LIMIT - 1 :])
    if other_total > 0:
        top_categories.append("Other")
        top_values.append(other_total)
    return top_categories, top_values


def _enumerate_plot_column_pairs(frame: pl.DataFrame) -> list[tuple[str, str]]:
    """Return category/value column pairs to try for chart generation.

    Args:
        frame: Query result data.

    Returns:
        Ordered list of ``(category_column, value_column)`` pairs.
    """
    preferred_category = _pick_category_column(frame)
    category_columns: list[str] = []
    if preferred_category is not None:
        category_columns.append(preferred_category)
    for column_name in frame.columns:
        if column_name in category_columns:
            continue
        if column_name in {
            "source_reference",
            "content_hash",
            "ingestion_timestamp",
            "_snapshot_table",
        }:
            continue
        if not _is_numeric_column(frame[column_name]):
            category_columns.append(column_name)

    value_columns = [
        column_name
        for column_name in frame.columns
        if column_name not in {"content_hash", "ingestion_timestamp", "_snapshot_table"}
        and _is_numeric_column(frame[column_name])
    ]

    pairs: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for category_column in category_columns:
        for value_column in value_columns:
            if category_column == value_column:
                continue
            pair = (category_column, value_column)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                pairs.append(pair)

    if not pairs and value_columns:
        pairs.append(("index", value_columns[0]))
    return pairs


def _extract_plot_series(
    frame: pl.DataFrame,
    category_column: str,
    value_column: str,
) -> tuple[list[str], list[float]] | None:
    """Build category/value lists when enough distinct points exist for charting.

    Args:
        frame: Query result data.
        category_column: Label column or ``index`` for row numbers.
        value_column: Numeric measure column.

    Returns:
        Category labels and values when at least ``_MINIMUM_CHART_POINTS`` exist;
        otherwise None.
    """
    if category_column == "index":
        plot_frame = frame.with_row_index(name="index").select(["index", value_column]).drop_nulls()
    else:
        plot_frame = frame.select([category_column, value_column]).drop_nulls()

    if plot_frame.is_empty():
        return None

    categories = [str(value) for value in plot_frame[category_column].to_list()]
    numeric_values = plot_frame[value_column].cast(pl.Float64, strict=False).to_list()
    values = [float(value) if value is not None else 0.0 for value in numeric_values]

    prepared_categories, prepared_values = _prepare_plot_series(categories, values)
    if len(prepared_categories) < _MINIMUM_CHART_POINTS:
        return None
    return prepared_categories, prepared_values


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
        categories: Category labels.
        values: Numeric values.
        chart_type: ``line``, ``bar``, or ``pie``.
    """
    figure, axis = plt.subplots(figsize=(8, 4.5))
    try:
        if chart_type == "line":
            axis.plot(range(len(values)), values, marker="o", linewidth=2, color="#1f4e79")
            axis.set_xticks(range(len(categories)))
            axis.set_xticklabels(categories, rotation=45, ha="right")
            axis.set_ylabel("Value")
            axis.grid(True, linestyle="--", alpha=0.35)
        elif chart_type == "bar":
            axis.bar(categories, values, color="#2e6da4")
            axis.tick_params(axis="x", rotation=45)
            axis.set_ylabel("Value")
            axis.grid(True, linestyle="--", alpha=0.35, axis="y")
        elif chart_type == "pie":
            axis.pie(
                values,
                labels=categories,
                autopct="%1.1f%%",
                startangle=90,
                textprops={"fontsize": 8},
            )
            axis.axis("equal")
        axis.set_title(title, fontsize=12, fontweight="bold")
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
    """Build line, bar, and pie charts from query result rows.

    Every non-empty result set produces all three chart types when a numeric
    measure and category axis can be derived.

    Args:
        records: Rows returned from ClickHouse queries.
        query: Original research question (used in chart titles).
        output_directory: Directory where PNG files are written.

    Returns:
        Chart metadata for PDF embedding (line, bar, pie when possible).
    """
    if not records:
        return []

    frame = pl.DataFrame(records)
    if frame.is_empty():
        return []

    plot_series: tuple[list[str], list[float], str] | None = None
    for category_column, value_column in _enumerate_plot_column_pairs(frame):
        series = _extract_plot_series(frame, category_column, value_column)
        if series is not None:
            categories, values = series
            plot_series = (categories, values, value_column)
            break

    if plot_series is None:
        logger.info(
            "Insufficient chart data: need at least %d points per chart",
            _MINIMUM_CHART_POINTS,
        )
        return []

    categories, values, value_column = plot_series
    line_categories, line_values = categories, values
    bar_categories, bar_values = categories, values
    pie_categories, pie_values = _prepare_pie_series(categories, values)

    if len(line_values) < _MINIMUM_CHART_POINTS:
        return []

    title_suffix = query[:60] + ("…" if len(query) > 60 else "")
    value_label = value_column.replace("_", " ").title()
    output_directory.mkdir(parents=True, exist_ok=True)

    artifacts: list[ChartArtifact] = []
    chart_series: list[tuple[str, list[str], list[float]]] = [
        ("line", line_categories, line_values),
        ("bar", bar_categories, bar_values),
        ("pie", pie_categories, pie_values),
    ]

    for chart_type, chart_categories, chart_values in chart_series:
        if len(chart_values) < _MINIMUM_CHART_POINTS:
            continue
        chart_title = f"{value_label} ({chart_type}) — {title_suffix}"
        chart_path = output_directory / f"chart_{value_column}_{chart_type}.png"
        _save_chart(
            output_path=chart_path,
            title=chart_title,
            categories=chart_categories,
            values=chart_values,
            chart_type=chart_type,
        )
        artifacts.append(
            ChartArtifact(
                title=chart_title,
                file_path=chart_path,
                chart_type=chart_type,
            )
        )

    logger.info(
        "Built %d chart(s): %s",
        len(artifacts),
        ", ".join(artifact.chart_type for artifact in artifacts),
    )
    return artifacts
