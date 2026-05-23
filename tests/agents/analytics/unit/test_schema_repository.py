"""Unit tests for the ClickHouse schema repository.

Tests use a mock clickhouse_connect client — no live database required.
Run and confirm these tests are FAILING before implementing schema_repository.py.
"""

from unittest.mock import MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)
from latam_investment_research_agent.agents.analytics.repositories.schema_repository import (
    get_all_table_schemas,
)


def _make_mock_client(
    table_names: list[str],
    describe_results: dict[str, list[tuple[str, str]]],
) -> MagicMock:
    """Build a mock clickhouse_connect async client.

    Args:
        table_names: Table names returned by SHOW TABLES.
        describe_results: Mapping of table_name to list of (column_name, type) tuples.

    Returns:
        A MagicMock configured to simulate the async client query responses.
    """
    client = MagicMock()

    async def mock_query(sql: str, *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        if "SHOW TABLES" in sql:
            result.result_rows = [(name,) for name in table_names]
        else:
            for table_name, columns in describe_results.items():
                if table_name in sql:
                    result.result_rows = columns
                    break
            else:
                result.result_rows = []
        return result

    client.query = mock_query
    return client


@pytest.mark.asyncio
async def test_get_all_table_schemas_returns_empty_list_when_no_tables() -> None:
    """get_all_table_schemas returns an empty list when ClickHouse has no tables."""
    client = _make_mock_client(table_names=[], describe_results={})
    result = await get_all_table_schemas(client)
    assert result == []


@pytest.mark.asyncio
async def test_get_all_table_schemas_maps_describe_output_to_table_schema() -> None:
    """get_all_table_schemas correctly maps DESCRIBE TABLE output to TableSchema objects."""
    client = _make_mock_client(
        table_names=["coffee_production"],
        describe_results={
            "coffee_production": [
                ("source_reference", "String"),
                ("ingestion_timestamp", "DateTime64(3, 'UTC')"),
                ("content_hash", "String"),
                ("year", "UInt16"),
                ("volume_tonnes", "Decimal(18,4)"),
            ]
        },
    )
    result = await get_all_table_schemas(client)

    assert len(result) == 1
    schema = result[0]
    assert isinstance(schema, TableSchema)
    assert schema.table_name == "coffee_production"
    assert len(schema.columns) == 5
    assert schema.columns[0] == ColumnInfo(column_name="source_reference", column_type="String")
    assert schema.columns[4] == ColumnInfo(
        column_name="volume_tonnes", column_type="Decimal(18,4)"
    )


@pytest.mark.asyncio
async def test_get_all_table_schemas_handles_multiple_tables() -> None:
    """get_all_table_schemas returns one TableSchema per table in SHOW TABLES."""
    client = _make_mock_client(
        table_names=["table_alpha", "table_beta"],
        describe_results={
            "table_alpha": [("value", "Float64")],
            "table_beta": [("amount", "Decimal(18,4)")],
        },
    )
    result = await get_all_table_schemas(client)
    assert len(result) == 2
    table_names_returned = {schema.table_name for schema in result}
    assert table_names_returned == {"table_alpha", "table_beta"}
