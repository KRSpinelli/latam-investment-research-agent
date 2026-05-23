"""Tests for template ClickHouse exploratory queries."""

from __future__ import annotations

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)
from latam_investment_research_agent.agents.analytics.services.exploratory_queries import (
    build_exploratory_queries,
)


def test_build_exploratory_queries_includes_snapshots_and_aggregates() -> None:
    schema = TableSchema(
        table_name="coffee_exports",
        columns=[
            ColumnInfo(column_name="source_reference", column_type="String"),
            ColumnInfo(column_name="ingestion_timestamp", column_type="DateTime64(3)"),
            ColumnInfo(column_name="content_hash", column_type="String"),
            ColumnInfo(column_name="year", column_type="Int32"),
            ColumnInfo(column_name="bags_exported", column_type="Int64"),
            ColumnInfo(column_name="terminal", column_type="String"),
        ],
    )

    queries = build_exploratory_queries([schema], row_limit=100, max_queries_per_table=4)

    assert len(queries) >= 2
    assert all(query.strip().upper().startswith("SELECT") for query in queries)
    assert any("coffee_exports" in query for query in queries)
    assert any("GROUP BY" in query.upper() for query in queries)
