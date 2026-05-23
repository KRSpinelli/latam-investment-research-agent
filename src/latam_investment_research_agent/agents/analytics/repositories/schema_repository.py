"""ClickHouse schema introspection repository.

Provides read-only access to the ClickHouse schema used by the table routing
node and the RAG query graph.  All queries target ClickHouse system tables and
never modify any data.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)

logger = logging.getLogger(__name__)


async def _describe_table(client: Any, table_name: str) -> TableSchema:
    """Describe one ClickHouse table and return its schema.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the table to describe.

    Returns:
        A ``TableSchema`` for the given table.
    """
    describe_result = await client.query(f"DESCRIBE TABLE {table_name}")
    columns = [
        ColumnInfo(column_name=row[0], column_type=row[1])
        for row in describe_result.result_rows
    ]
    logger.debug(
        "  %s: %d column(s) — %s",
        table_name,
        len(columns),
        ", ".join(column.column_name for column in columns),
    )
    return TableSchema(table_name=table_name, columns=columns)


async def get_all_table_schemas(client: Any) -> list[TableSchema]:
    """Retrieve the schema of every user table in the configured ClickHouse database.

    Issues ``SHOW TABLES`` to enumerate tables, then ``DESCRIBE TABLE`` for each
    one to collect column names and types.  Results are returned as a list of
    ``TableSchema`` objects suitable for passing to the LLM routing and query
    assembly nodes.

    Args:
        client: An async-compatible clickhouse_connect client instance.

    Returns:
        A list of ``TableSchema`` objects, one per table.  Returns an empty list
        if the database contains no tables.

    Example:
        import clickhouse_connect
        client = await clickhouse_connect.get_async_client(host="localhost")
        schemas = await get_all_table_schemas(client)
        for schema in schemas:
            print(schema.table_name, [col.column_name for col in schema.columns])
    """
    logger.info("Introspecting ClickHouse schema...")
    show_result = await client.query("SHOW TABLES")
    table_names: list[str] = [row[0] for row in show_result.result_rows]

    if not table_names:
        logger.info("No tables found in ClickHouse database")
        return []

    logger.info("Found %d table(s): %s", len(table_names), ", ".join(table_names))
    return list(
        await asyncio.gather(
            *[_describe_table(client, table_name) for table_name in table_names]
        )
    )
