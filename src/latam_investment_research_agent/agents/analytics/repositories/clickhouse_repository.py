"""ClickHouse data repository for the ingestion agent.

Handles all write operations: creating tables with the correct schema and
audit columns, evolving schemas as new columns are encountered, and inserting
rows with content-hash-based deduplication.

No ORM is used.  All SQL is constructed explicitly and parameterised where
possible to prevent injection.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from latam_investment_research_agent.agents.analytics.constants import (
    CLICKHOUSE_ALTER_MAX_RETRIES,
    CLICKHOUSE_ALTER_RETRY_BASE_DELAY_SECONDS,
    CLICKHOUSE_ORDER_BY_COLUMNS,
    CLICKHOUSE_TABLE_ENGINE,
    MANDATORY_AUDIT_COLUMNS,
)
from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition
from latam_investment_research_agent.agents.analytics.repositories.row_preparation import (
    _quote_column_identifier,
    coerce_cell_value,
    normalize_rows,
)

logger = logging.getLogger(__name__)


def _is_clickhouse_alter_retryable(error: BaseException) -> bool:
    """Return True when ClickHouse Cloud suggests retrying an ``ALTER`` (code 517).

    Args:
        error: Exception raised by clickhouse_connect.

    Returns:
        True if the error message indicates a transient replica metadata lag.
    """
    message = str(error)
    return (
        "CANNOT_ASSIGN_ALTER" in message
        or "code: 517" in message
        or "doesn't catchup with latest ALTER" in message
    )


async def _run_clickhouse_command_with_alter_retry(
    client: Any,
    sql: str,
    *,
    operation_label: str,
) -> None:
    """Run a ClickHouse command, retrying transient ``ALTER`` replica lag errors.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        sql: SQL statement to execute.
        operation_label: Short description for log messages.

    Raises:
        Exception: The last error if all retry attempts are exhausted.
    """
    for attempt in range(1, CLICKHOUSE_ALTER_MAX_RETRIES + 1):
        try:
            await client.command(sql)
            return
        except Exception as error:
            if (
                not _is_clickhouse_alter_retryable(error)
                or attempt >= CLICKHOUSE_ALTER_MAX_RETRIES
            ):
                raise
            delay_seconds = CLICKHOUSE_ALTER_RETRY_BASE_DELAY_SECONDS * (
                2 ** (attempt - 1)
            )
            logger.warning(
                "ClickHouse ALTER retry %d/%d for %s: %s; sleeping %.1fs",
                attempt,
                CLICKHOUSE_ALTER_MAX_RETRIES,
                operation_label,
                error,
                delay_seconds,
            )
            await asyncio.sleep(delay_seconds)


def _format_clickhouse_datetime64_utc(moment: datetime) -> str:
    """Format a UTC moment for ClickHouse ``DateTime64(3, 'UTC')`` columns.

    ClickHouse accepts ``YYYY-MM-DD HH:MM:SS.sss`` but not ISO 8601 timezone
    suffixes such as ``+00:00``.

    Args:
        moment: A timezone-aware or naive datetime in UTC.

    Returns:
        A string with millisecond precision, e.g. ``2026-05-23 18:09:04.896``.
    """
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]


def _escape_sql_string(value: str) -> str:
    """Escape a string for safe inclusion in a ClickHouse SQL literal.

    Args:
        value: Raw string value.

    Returns:
        Value with single quotes doubled for SQL string literals.
    """
    return value.replace("'", "''")


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
        f"{_quote_column_identifier(column.column_name)} {column.clickhouse_type}"
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


async def get_table_column_types(client: Any, table_name: str) -> dict[str, str]:
    """Return a mapping of column name to ClickHouse type for one table.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Table to describe.

    Returns:
        Dict of column_name → type string from ``DESCRIBE TABLE``.
    """
    describe_result = await client.query(f"DESCRIBE TABLE {table_name}")
    return {row[0]: row[1] for row in describe_result.result_rows}


async def ensure_row_columns_exist(
    client: Any,
    table_name: str,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    """Add any row keys missing from the table as ``String`` columns.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Target table name.
        rows: Normalized row dicts for one dataset.

    Returns:
        Updated column name → type mapping after any ``ALTER TABLE`` calls.
    """
    column_types = await get_table_column_types(client, table_name)
    row_keys: set[str] = set()
    for row in rows:
        row_keys.update(row.keys())
    row_keys -= set(MANDATORY_AUDIT_COLUMNS)

    missing_keys = sorted(key for key in row_keys if key not in column_types)
    if missing_keys:
        new_columns = [
            ColumnDefinition(
                column_name=column_key,
                clickhouse_type="String",
                description="Auto-added to match extracted row keys.",
            )
            for column_key in missing_keys
        ]
        await alter_table_add_columns(client, table_name, new_columns)
        column_types = await get_table_column_types(client, table_name)

    return column_types


async def _alter_table_add_single_column(
    client: Any,
    table_name: str,
    column: ColumnDefinition,
) -> None:
    """Issue one ``ALTER TABLE ... ADD COLUMN`` statement.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the existing table to modify.
        column: Column definition to add.
    """
    quoted_column = _quote_column_identifier(column.column_name)
    sql = (
        f"ALTER TABLE {table_name} "
        f"ADD COLUMN IF NOT EXISTS {quoted_column} {column.clickhouse_type} "
        f"DEFAULT ''"
    )
    logger.info(
        "Adding column '%s' (%s) to table '%s'",
        column.column_name,
        column.clickhouse_type,
        table_name,
    )
    await _run_clickhouse_command_with_alter_retry(
        client,
        sql,
        operation_label=f"ADD COLUMN {column.column_name} on {table_name}",
    )


async def alter_table_add_columns(
    client: Any,
    table_name: str,
    new_columns: list[ColumnDefinition],
) -> None:
    """Add new columns to an existing ClickHouse table.

    Issues one ``ALTER TABLE ... ADD COLUMN`` statement per new column with a
    default value of an empty string (compatible with most ClickHouse types via
    implicit casting).  Column additions run concurrently.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_name: Name of the existing table to modify.
        new_columns: Columns to add.  Must not include audit column names.
    """
    if not new_columns:
        return
    for column in new_columns:
        await _alter_table_add_single_column(client, table_name, column)


async def create_tables_parallel(
    client: Any,
    table_specs: list[tuple[str, list[ColumnDefinition]]],
) -> None:
    """Create multiple ClickHouse tables concurrently.

    Each spec is ``(table_name, data_columns)``.  Uses ``CREATE TABLE IF NOT EXISTS``
    so duplicate table names in the spec list are safe.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        table_specs: Unique or duplicate table creation requests.
    """
    if not table_specs:
        return
    await asyncio.gather(
        *[create_table(client, table_name, columns) for table_name, columns in table_specs]
    )


async def alter_tables_parallel(
    client: Any,
    alter_specs: list[tuple[str, list[ColumnDefinition]]],
) -> None:
    """Add columns to multiple tables concurrently.

    Args:
        client: An async-compatible clickhouse_connect client instance.
        alter_specs: List of ``(table_name, new_columns)`` pairs.
    """
    if not alter_specs:
        return
    await asyncio.gather(
        *[
            alter_table_add_columns(client, table_name, new_columns)
            for table_name, new_columns in alter_specs
        ]
    )


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

    normalized_rows = normalize_rows(rows)
    column_types = await ensure_row_columns_exist(client, table_name, normalized_rows)

    ingestion_timestamp = _format_clickhouse_datetime64_utc(datetime.now(tz=UTC))
    enriched_rows: list[dict[str, Any]] = []

    for row in normalized_rows:
        content_hash = _compute_content_hash(row)
        enriched_row = {
            "source_reference": source_reference,
            "ingestion_timestamp": ingestion_timestamp,
            "content_hash": content_hash,
            **row,
        }
        enriched_rows.append(enriched_row)

    escaped_reference = _escape_sql_string(source_reference)
    hash_query = (
        f"SELECT content_hash FROM {table_name} "
        f"WHERE source_reference = '{escaped_reference}'"
    )
    hash_result = await client.query(hash_query)
    existing_hashes = {row[0] for row in hash_result.result_rows}

    new_rows = [
        enriched_row
        for enriched_row in enriched_rows
        if enriched_row["content_hash"] not in existing_hashes
    ]
    rows_skipped = len(enriched_rows) - len(new_rows)

    logger.info(
        "Inserting up to %d row(s) into '%s' (with deduplication, %d duplicate(s) skipped)",
        len(new_rows),
        table_name,
        rows_skipped,
    )

    if not new_rows:
        logger.info("Write complete for '%s': 0 inserted, %d duplicate(s) skipped", table_name, rows_skipped)
        return 0

    insert_column_order = [
        column_name
        for column_name in column_types
        if column_name in new_rows[0]
    ]
    insert_data = [
        [
            coerce_cell_value(row.get(column_name), column_types[column_name])
            for column_name in insert_column_order
        ]
        for row in new_rows
    ]
    await client.insert(table_name, insert_data, column_names=insert_column_order)

    rows_written = len(new_rows)
    logger.info(
        "Write complete for '%s': %d inserted, %d duplicate(s) skipped",
        table_name,
        rows_written,
        rows_skipped,
    )
    return rows_written
