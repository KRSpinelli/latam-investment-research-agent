"""RAG graph node: execute SQL queries against ClickHouse.

Validates SELECT-only guard a second time, executes each query, merges
results, and applies row-limit truncation.  Per-query failures are logged
and skipped rather than propagated — the node never raises.

Queries run concurrently up to ``max_concurrent_queries`` (bounded by a
semaphore) so large query batches do not execute one-by-one.

See: contracts/rag_query_graph.md § Read-Only Guarantee
     contracts/rag_query_graph.md § Error Behaviour
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from latam_investment_research_agent.agents.analytics.models.domain import TableSchema
from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState
from latam_investment_research_agent.agents.analytics.services.sql_query_repair import (
    extract_table_name,
    repair_clickhouse_select,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CONCURRENT_QUERIES = 8


@dataclass(frozen=True)
class _QueryExecutionOutcome:
    """Result of attempting one SELECT against ClickHouse."""

    sql_query: str
    rows: list[dict[str, Any]]
    error: Exception | None = None


async def execute_select_query(
    clickhouse_client: Any,
    sql_query: str,
) -> list[dict[str, Any]]:
    """Execute a single SELECT query and return rows as a list of dicts.

    Args:
        clickhouse_client: An async clickhouse_connect client instance.
        sql_query: A validated SELECT query string.

    Returns:
        A list of row dicts where keys are column names.
    """
    query_result = await clickhouse_client.query(sql_query)
    column_names = query_result.column_names
    return [dict(zip(column_names, row, strict=True)) for row in query_result.result_rows]


async def _execute_single_query(
    clickhouse_client: Any,
    sql_query: str,
    table_schema: TableSchema | None,
) -> _QueryExecutionOutcome:
    """Repair, validate, and run one SELECT query.

    Args:
        clickhouse_client: Async ClickHouse client.
        sql_query: Candidate SQL string.
        table_schema: Optional schema for SQL repair.

    Returns:
        Outcome with rows or a captured exception.
    """
    repaired_query = repair_clickhouse_select(sql_query, table_schema)
    if not repaired_query.strip().upper().startswith("SELECT"):
        logger.error(
            "execute_queries_node: rejecting non-SELECT query (SELECT-only guard): %r",
            repaired_query[:120],
        )
        return _QueryExecutionOutcome(sql_query=repaired_query, rows=[])

    try:
        rows = await execute_select_query(clickhouse_client, repaired_query)
        return _QueryExecutionOutcome(sql_query=repaired_query, rows=rows)
    except Exception as error:
        return _QueryExecutionOutcome(
            sql_query=repaired_query,
            rows=[],
            error=error,
        )


async def execute_queries_node(
    state: RAGQueryState,
    clickhouse_client: Any,
    *,
    max_concurrent_queries: int = _DEFAULT_MAX_CONCURRENT_QUERIES,
) -> dict[str, Any]:
    """Execute all assembled SELECT queries and merge the results.

    Re-validates that every query starts with SELECT before execution —
    never trust prior validation alone.  Per-query failures are logged and
    the node continues processing remaining queries.

    Queries are executed concurrently (bounded by ``max_concurrent_queries``).

    If the total number of result rows exceeds ``state["export_row_limit"]``,
    the results are truncated to that limit and ``was_truncated`` is set to
    ``True``.

    Args:
        state: The current RAG query graph state.
        clickhouse_client: An async clickhouse_connect client instance.
        max_concurrent_queries: Maximum in-flight ClickHouse SELECT calls.

    Returns:
        A dict with:
        - ``query_result_records`` (list[dict[str, Any]]): merged rows.
        - ``was_truncated`` (bool): True when results were truncated.
    """
    sql_queries: list[str] = state.get("assembled_sql_queries", [])
    export_row_limit: int = state.get("export_row_limit", 10_000)
    available_schemas: list[TableSchema] = state.get("available_table_schemas", [])
    schemas_by_table = {schema.table_name.lower(): schema for schema in available_schemas}

    if not sql_queries:
        return {"query_result_records": [], "was_truncated": False}

    concurrency_limit = max(1, max_concurrent_queries)
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def run_bounded(sql_query: str) -> _QueryExecutionOutcome:
        table_name = extract_table_name(sql_query)
        table_schema = schemas_by_table.get(table_name) if table_name else None
        async with semaphore:
            return await _execute_single_query(clickhouse_client, sql_query, table_schema)

    logger.info(
        "Executing %d ClickHouse queries with concurrency=%d",
        len(sql_queries),
        concurrency_limit,
    )
    outcomes = await asyncio.gather(*(run_bounded(sql_query) for sql_query in sql_queries))

    all_rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        if outcome.error is not None:
            logger.error(
                "Query execution failed (skipping): %r — %s",
                outcome.sql_query[:80],
                outcome.error,
            )
            continue
        all_rows.extend(outcome.rows)
        logger.info(
            "Query returned %d row(s): %r",
            len(outcome.rows),
            outcome.sql_query[:80],
        )

    was_truncated = len(all_rows) > export_row_limit
    if was_truncated:
        logger.info(
            "Result set (%d rows) exceeds export_row_limit (%d) — truncating.",
            len(all_rows),
            export_row_limit,
        )
        all_rows = all_rows[:export_row_limit]

    return {
        "query_result_records": all_rows,
        "was_truncated": was_truncated,
    }
