"""Unit tests for parallel ClickHouse query execution in the RAG graph."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.nodes.rag.execute_queries_node import (
    execute_queries_node,
)


@pytest.mark.asyncio
async def test_execute_queries_node_runs_queries_concurrently() -> None:
    """Multiple SELECT statements execute in parallel (bounded by concurrency)."""
    concurrent_calls = 0
    peak_concurrent_calls = 0
    lock = asyncio.Lock()

    async def slow_query(_client: MagicMock, _sql_query: str) -> list[dict[str, str]]:
        nonlocal concurrent_calls, peak_concurrent_calls
        async with lock:
            concurrent_calls += 1
            peak_concurrent_calls = max(peak_concurrent_calls, concurrent_calls)
        await asyncio.sleep(0.05)
        async with lock:
            concurrent_calls -= 1
        return [{"value": "1"}]

    clickhouse_client = MagicMock()
    sql_queries = [f"SELECT {index} FROM export_revenue LIMIT 1" for index in range(6)]

    with patch(
        "latam_investment_research_agent.agents.analytics.nodes.rag"
        ".execute_queries_node.execute_select_query",
        side_effect=slow_query,
    ):
        result = await execute_queries_node(
            {
                "assembled_sql_queries": sql_queries,
                "export_row_limit": 10_000,
                "available_table_schemas": [],
            },
            clickhouse_client,
            max_concurrent_queries=4,
        )

    assert len(result["query_result_records"]) == 6
    assert peak_concurrent_calls > 1
