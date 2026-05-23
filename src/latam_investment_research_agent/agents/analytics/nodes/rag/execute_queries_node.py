"""RAG graph node: execute SQL queries against ClickHouse.

Validates SELECT-only guard a second time, executes each query, merges
results, and applies row-limit truncation.  Per-query failures are logged
and skipped rather than propagated — the node never raises.

See: contracts/rag_query_graph.md § Read-Only Guarantee
     contracts/rag_query_graph.md § Error Behaviour
"""

from __future__ import annotations

import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState

logger = logging.getLogger(__name__)


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


async def execute_queries_node(
    state: RAGQueryState,
    clickhouse_client: Any,
) -> dict[str, Any]:
    """Execute all assembled SELECT queries and merge the results.

    Re-validates that every query starts with SELECT before execution —
    never trust prior validation alone.  Per-query failures are logged and
    the node continues processing remaining queries.

    If the total number of result rows exceeds ``state["export_row_limit"]``,
    the results are truncated to that limit and ``was_truncated`` is set to
    ``True``.

    Args:
        state: The current RAG query graph state.
        clickhouse_client: An async clickhouse_connect client instance.

    Returns:
        A dict with:
        - ``query_result_records`` (list[dict[str, Any]]): merged rows.
        - ``was_truncated`` (bool): True when results were truncated.
    """
    sql_queries: list[str] = state.get("assembled_sql_queries", [])
    export_row_limit: int = state.get("export_row_limit", 10_000)

    all_rows: list[dict[str, Any]] = []

    for sql_query in sql_queries:
        if not sql_query.strip().upper().startswith("SELECT"):
            logger.error(
                "execute_queries_node: rejecting non-SELECT query (SELECT-only guard): %r",
                sql_query[:120],
            )
            continue

        try:
            rows = await execute_select_query(clickhouse_client, sql_query)
            all_rows.extend(rows)
            logger.info("Query returned %d row(s): %r", len(rows), sql_query[:80])
        except Exception as exc:
            logger.error("Query execution failed (skipping): %r — %s", sql_query[:80], exc)

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
