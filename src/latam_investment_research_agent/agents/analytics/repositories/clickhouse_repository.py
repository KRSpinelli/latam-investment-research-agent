"""ClickHouse data repository for the ingestion agent.

Handles all write operations: creating tables with the correct schema and
audit columns, evolving schemas as new columns are encountered, and inserting
rows with content-hash-based deduplication.

No ORM is used.  All SQL is constructed explicitly and parameterised where
possible to prevent injection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from latam_investment_research_agent.agents.analytics.constants import (
    CLICKHOUSE_ORDER_BY_COLUMNS,
    CLICKHOUSE_TABLE_ENGINE,
    MANDATORY_AUDIT_COLUMNS,
)
from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition

logger = logging.getLogger(__name__)


def _compute_content_hash(row: dict[str, Any]) -> str:
    """Compute a full SHA-256 content hash for one row.

    The hash is derived from the canonical JSON representation of the row
    (keys sorted, all values coerced to strings via ``default=str``).  The
    full 64-character hex digest is returned — no truncation.

    Args:
        row: A dictionary of column_name → value for one data row.

    Returns:
        A 64-character lowercase hexadecimal SHA-256 digest.
    """
    canonical_string = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(canonical_string.encode()).hexdigest()


def _build_create_table_sql(
    table_name: str,
    data_columns: list[ColumnDefinition],
) -> str:
    """Build a ``CREATE TABLE IF NOT EXISTS`` SQL statement.

    Mandatory audit columns are always prepended to the column list regardless
    of what the caller supplies.  The table uses ``MergeTree()`` engine with
    ``ORDER BY (source_reference, content_hash, ingestion_timestamp)``.

    Args:
        table_name: The name of the ClickHouse table to create.
        data_columns: Data columns proposed by the LLM routing decision.
            Must not include audit column names.

    Returns:
        A complete ``CREATE TABLE IF NOT EXISTS`` SQL statement as a string.
    """
    audit_column_definitions = [
        "source_reference String",
        "ingestion_timestamp DateTime64(3, 'UTC')",
        "content_hash String",
    ]
    data_column_definitions = [
        f"{column.column_name} {column.clickhouse_type}"
        for column in data_columns
    ]
    all_column_definitions = audit_column_definitions + data_column_definitions
    column_block = ",\n    ".join(all_column_definitions)
    order_by_clause = ", ".join(CLICKHOUSE_ORDER_BY_COLUMNS)

    return (
        f"CREATE TABLE IF NOT EXISTS {table_name}\n"
        f"(\n"
        f"    {column_block}\n"
        f")\n"
        f"ENGINE = {CLICKHOUSE_TABLE_ENGINE}\n"
        f"ORDER BY ({order_by_clause})"
    )


async def create_table(
    client: Any,
    table_name: str,
    data_columns: list[ColumnDefinition],
) -> None:
    """Create a new ClickHouse table with mandatory audit columns.

    Uses ``CREATE TABLE IF NOT EXISTS`` so the call is idempotent.  Mandatory
    audit columns (``source_reference``, ``ingestion_timestamp``,
    ``content_hash``) are always prepended; they must not appear in
    ``data_columns``.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the table to create.
        data_columns: Column definitions proposed by the LLM routing decision.
            Must not include any of the mandatory audit column names.

    Raises:
        ValueError: If any column in ``data_columns`` uses a reserved audit
            column name.
    """
    for column in data_columns:
        if column.column_name in MANDATORY_AUDIT_COLUMNS:
            raise ValueError(
                f"Column '{column.column_name}' is a reserved audit column and "
                "must not be included in proposed data columns."
            )

    sql = _build_create_table_sql(table_name, data_columns)
    logger.info("Creating ClickHouse table '%s'", table_name)
    await client.command(sql)


async def alter_table_add_columns(
    client: Any,
    table_name: str,
    new_columns: list[ColumnDefinition],
) -> None:
    """Add new columns to an existing ClickHouse table.

    Issues one ``ALTER TABLE ... ADD COLUMN`` statement per new column with a
    default value of an empty string (compatible with most ClickHouse types via
    implicit casting).

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the existing table to modify.
        new_columns: Columns to add.  Must not include audit column names.
    """
    for column in new_columns:
        sql = (
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN IF NOT EXISTS {column.column_name} {column.clickhouse_type} "
            f"DEFAULT ''"
        )
        logger.info(
            "Adding column '%s' (%s) to table '%s'",
            column.column_name,
            column.clickhouse_type,
            table_name,
        )
        await client.command(sql)


async def insert_rows_deduplicated(
    client: Any,
    table_name: str,
    rows: list[dict[str, Any]],
    source_reference: str,
) -> int:
    """Insert rows into a ClickHouse table, skipping duplicates.

    Each row receives:
    - ``source_reference``: the URL or file path of the source document.
    - ``ingestion_timestamp``: the current UTC time.
    - ``content_hash``: a full SHA-256 digest of the row content.

    Rows whose ``(source_reference, content_hash)`` pair already exists in the
    table are skipped.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the ClickHouse table to write to.
        rows: Data rows as dicts of column_name → value.
        source_reference: URL or file path of the source document.

    Returns:
        The number of rows actually written (may be less than ``len(rows)``
        if duplicates were detected and skipped).
    """
    if not rows:
        return 0

    ingestion_timestamp = datetime.now(tz=UTC).isoformat()
    enriched_rows: list[dict[str, Any]] = []

    for row in rows:
        content_hash = _compute_content_hash(row)
        enriched_row = {
            "source_reference": source_reference,
            "ingestion_timestamp": ingestion_timestamp,
            "content_hash": content_hash,
            **row,
        }
        enriched_rows.append(enriched_row)

    column_names = list(enriched_rows[0].keys())
    column_list = ", ".join(column_names)

    logger.info(
        "Inserting up to %d row(s) into '%s' (with deduplication)",
        len(enriched_rows),
        table_name,
    )

    rows_written = 0
    rows_skipped = 0
    for enriched_row in enriched_rows:
        values = ", ".join(
            f"'{str(enriched_row[col]).replace(chr(39), chr(39) + chr(39))}'"
            for col in column_names
        )
        sql = (
            f"INSERT INTO {table_name} ({column_list}) "
            f"SELECT {values} "
            f"WHERE ('{enriched_row['source_reference']}', '{enriched_row['content_hash']}') "
            f"NOT IN (SELECT source_reference, content_hash FROM {table_name})"
        )
        result = await client.command(sql)
        # clickhouse-connect returns the number of rows written for INSERT statements
        written = result if isinstance(result, int) else 1
        if written:
            rows_written += 1
        else:
            rows_skipped += 1

    logger.info(
        "Write complete for '%s': %d inserted, %d duplicate(s) skipped",
        table_name,
        rows_written,
        rows_skipped,
    )
    return rows_written
