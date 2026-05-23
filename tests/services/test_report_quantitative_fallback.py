"""Tests for guaranteed ClickHouse quantitative reads."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    DatasetIngestionResult,
    TableSchema,
)
from latam_investment_research_agent.schemas.research import IngestionSummaryResponse
from latam_investment_research_agent.services.report_quantitative_fallback import (
    _order_tables_for_query,
    ensure_quantitative_data,
    fetch_ingested_table_snapshots,
)


def _mock_query_result(column_names: list[str], rows: list[tuple]) -> MagicMock:
    result = MagicMock()
    result.column_names = column_names
    result.result_rows = rows
    return result


@pytest.mark.asyncio
async def test_fetch_ingested_table_snapshots_reads_successful_tables() -> None:
    """Fallback should query each table from ingestion summaries."""
    summaries = [
        IngestionSummaryResponse(
            source_reference="https://example.com/a",
            total_datasets_found=1,
            datasets_succeeded=[
                DatasetIngestionResult(
                    dataset_name="Exports",
                    target_table_name="coffee_exports",
                    routing_action="append",
                    rows_written=3,
                )
            ],
            datasets_failed=[],
        )
    ]

    clickhouse_client = AsyncMock()
    clickhouse_client.query = AsyncMock(
        return_value=_mock_query_result(
            ["source_reference", "year", "value"],
            [("https://example.com/a", 2024, 100)],
        )
    )

    rows, sql_queries = await fetch_ingested_table_snapshots(
        summaries,
        clickhouse_client,
        row_limit_per_table=10,
    )

    assert len(rows) == 1
    assert rows[0]["year"] == 2024
    assert rows[0]["_snapshot_table"] == "coffee_exports"
    assert len(sql_queries) == 1
    assert "coffee_exports" in sql_queries[0]


def test_order_tables_for_query_prioritizes_matching_names() -> None:
    """Coffee-related tables should rank above unrelated tables."""
    schemas_by_name = {
        "redex_coffee_export_data": TableSchema(
            table_name="redex_coffee_export_data",
            columns=[ColumnInfo(column_name="bags_exported", column_type="Int64")],
        ),
        "unrelated_metrics": TableSchema(
            table_name="unrelated_metrics",
            columns=[ColumnInfo(column_name="value", column_type="Float64")],
        ),
    }
    ordered = _order_tables_for_query(
        list(schemas_by_name.keys()),
        schemas_by_name,
        "Brazil coffee export revenues by year",
    )
    assert ordered[0] == "redex_coffee_export_data"


@pytest.mark.asyncio
async def test_ensure_quantitative_data_escalates_to_full_schema() -> None:
    """When RAG returns nothing and ingestion is empty, probe all ClickHouse tables."""
    coffee_schema = TableSchema(
        table_name="redex_coffee_export_data",
        columns=[
            ColumnInfo(column_name="year", column_type="Int32"),
            ColumnInfo(column_name="bags_exported", column_type="Int64"),
            ColumnInfo(column_name="source_reference", column_type="String"),
            ColumnInfo(column_name="ingestion_timestamp", column_type="DateTime64(3)"),
        ],
    )

    clickhouse_client = AsyncMock()
    clickhouse_client.query = AsyncMock(
        return_value=_mock_query_result(
            ["source_reference", "year", "bags_exported", "_snapshot_table"],
            [("https://example.com/x", 2023, 1000, "redex_coffee_export_data")],
        )
    )

    with patch(
        "latam_investment_research_agent.services.report_quantitative_fallback.get_all_table_schemas",
        new_callable=AsyncMock,
        return_value=[coffee_schema],
    ):
        bundle = await ensure_quantitative_data(
            "Brazil coffee export revenues",
            [],
            clickhouse_client,
            existing_rows=[],
            minimum_rows=1,
        )

    assert len(bundle.rows) >= 1
    assert bundle.data_source_note
    assert len(bundle.sql_queries) >= 1


@pytest.mark.asyncio
async def test_ensure_quantitative_data_keeps_sufficient_rag_rows() -> None:
    """Do not run fallbacks when RAG already returned enough rows."""
    existing = [{"year": 2024, "value": index} for index in range(15)]
    clickhouse_client = AsyncMock()

    bundle = await ensure_quantitative_data(
        "coffee exports",
        [],
        clickhouse_client,
        existing_rows=existing,
        minimum_rows=10,
    )

    assert len(bundle.rows) == 15
    clickhouse_client.query.assert_not_called()
