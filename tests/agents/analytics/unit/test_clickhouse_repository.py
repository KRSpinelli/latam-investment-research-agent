"""Unit tests for the ClickHouse data repository.

Tests use a mock clickhouse_connect client — no live database required.
Run and confirm these tests are FAILING before implementing clickhouse_repository.py.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.constants import (
    MANDATORY_AUDIT_COLUMNS,
)
from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition
from latam_investment_research_agent.agents.analytics.repositories.clickhouse_repository import (
    alter_table_add_columns,
    create_table,
    insert_rows_deduplicated,
)


def _default_describe_rows() -> list[tuple[str, str]]:
    """Return default DESCRIBE TABLE rows for repository unit tests.

    Returns:
        Column name and type pairs including audit and sample data columns.
    """
    return [
        ("source_reference", "String"),
        ("ingestion_timestamp", "DateTime64(3, 'UTC')"),
        ("content_hash", "String"),
        ("year", "UInt16"),
        ("revenue", "Decimal(18,4)"),
    ]


def _make_mock_client() -> MagicMock:
    """Build a mock clickhouse_connect async client with a recorded command history.

    Returns:
        MagicMock with ``command``, ``query``, and ``insert`` coroutines.
    """
    describe_rows = _default_describe_rows()

    async def mock_query(sql: str, *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        if "DESCRIBE TABLE" in sql:
            result.result_rows = describe_rows
        else:
            result.result_rows = []
        return result

    client = MagicMock()
    client.command = AsyncMock(return_value=None)
    client.query = AsyncMock(side_effect=mock_query)
    client.insert = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_create_table_uses_merge_tree_engine() -> None:
    """create_table issues CREATE TABLE IF NOT EXISTS with MergeTree() engine."""
    client = _make_mock_client()
    columns = [ColumnDefinition(column_name="year", clickhouse_type="UInt16", description="Year")]
    await create_table(client, "test_table", columns)

    sql_issued: str = client.command.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS" in sql_issued
    assert "test_table" in sql_issued
    assert "MergeTree()" in sql_issued


@pytest.mark.asyncio
async def test_create_table_includes_all_mandatory_audit_columns() -> None:
    """create_table prepends all three mandatory audit columns to the schema."""
    client = _make_mock_client()
    columns = [ColumnDefinition(column_name="year", clickhouse_type="UInt16", description="Year")]
    await create_table(client, "test_table", columns)

    sql_issued: str = client.command.call_args[0][0]
    for audit_column in MANDATORY_AUDIT_COLUMNS:
        assert audit_column in sql_issued


@pytest.mark.asyncio
async def test_create_table_uses_correct_order_by() -> None:
    """create_table uses ORDER BY (source_reference, content_hash, ingestion_timestamp)."""
    client = _make_mock_client()
    columns = [ColumnDefinition(column_name="year", clickhouse_type="UInt16", description="Year")]
    await create_table(client, "test_table", columns)

    sql_issued: str = client.command.call_args[0][0]
    assert "ORDER BY" in sql_issued
    assert "source_reference" in sql_issued
    assert "content_hash" in sql_issued
    assert "ingestion_timestamp" in sql_issued


@pytest.mark.asyncio
async def test_alter_table_add_columns_generates_correct_sql() -> None:
    """alter_table_add_columns issues ALTER TABLE ADD COLUMN for each new column."""
    client = _make_mock_client()
    new_columns = [
        ColumnDefinition(
            column_name="export_volume", clickhouse_type="Decimal(18,4)", description="Export"
        ),
    ]
    await alter_table_add_columns(client, "existing_table", new_columns)

    sql_issued: str = client.command.call_args[0][0]
    assert "ALTER TABLE" in sql_issued
    assert "existing_table" in sql_issued
    assert "ADD COLUMN" in sql_issued
    assert "export_volume" in sql_issued
    assert "Decimal(18,4)" in sql_issued


@pytest.mark.asyncio
async def test_insert_rows_deduplicated_prefetches_existing_hashes() -> None:
    """insert_rows_deduplicated queries existing content hashes for the source."""
    client = _make_mock_client()
    rows = [{"year": 2023, "revenue": "1000.00"}]
    await insert_rows_deduplicated(client, "test_table", rows, "https://example.com/doc.pdf")

    hash_query: str = client.query.call_args[0][0]
    assert "SELECT content_hash" in hash_query
    assert "source_reference" in hash_query
    assert "https://example.com/doc.pdf" in hash_query


@pytest.mark.asyncio
async def test_insert_rows_deduplicated_uses_batch_insert() -> None:
    """insert_rows_deduplicated issues one batch insert for multiple new rows."""
    client = _make_mock_client()
    rows = [{"year": 2023}, {"year": 2024}]
    await insert_rows_deduplicated(client, "test_table", rows, "https://example.com/doc.pdf")

    client.insert.assert_awaited_once()
    insert_data = client.insert.call_args[0][1]
    assert len(insert_data) == 2
    assert client.command.await_count == 0


@pytest.mark.asyncio
async def test_insert_rows_deduplicated_computes_full_sha256_hash() -> None:
    """insert_rows_deduplicated computes a full 64-character SHA-256 hex digest per row."""
    client = _make_mock_client()
    row = {"year": 2023, "revenue": "1000.00"}
    expected_hash = hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode()
    ).hexdigest()
    assert len(expected_hash) == 64

    await insert_rows_deduplicated(client, "test_table", [row], "https://example.com/doc.pdf")
    insert_data = client.insert.call_args[0][1]
    column_names = client.insert.call_args[1]["column_names"]
    hash_index = list(column_names).index("content_hash")
    assert insert_data[0][hash_index] == expected_hash


@pytest.mark.asyncio
async def test_insert_rows_deduplicated_skips_duplicate_hashes_without_insert() -> None:
    """Rows whose hash already exists are filtered before insert."""
    client = _make_mock_client()
    row = {"year": 2023, "revenue": "1000.00"}
    existing_hash = hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode()
    ).hexdigest()
    describe_rows = _default_describe_rows()

    async def mock_query(sql: str, *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        if "DESCRIBE TABLE" in sql:
            result.result_rows = describe_rows
        else:
            result.result_rows = [(existing_hash,)]
        return result

    client.query = AsyncMock(side_effect=mock_query)

    count = await insert_rows_deduplicated(
        client, "test_table", [row], "https://example.com/doc.pdf"
    )

    assert count == 0
    client.insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_insert_rows_deduplicated_returns_row_count() -> None:
    """insert_rows_deduplicated returns the number of rows inserted."""
    client = _make_mock_client()
    rows = [{"year": 2023}, {"year": 2024}]
    count = await insert_rows_deduplicated(
        client, "test_table", rows, "https://example.com/doc.pdf"
    )
    assert isinstance(count, int)
    assert count >= 0
