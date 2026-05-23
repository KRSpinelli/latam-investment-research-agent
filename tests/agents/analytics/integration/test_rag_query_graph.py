"""Integration tests for the RAG query LangGraph.

Tests US4 acceptance scenarios: natural-language question → CSV export with
rationale and SQL.  Dependencies (ClickHouse, LLM) are mocked so these tests
do not require a live external service.

See: spec.md § User Story 4 Acceptance Scenarios
     contracts/rag_query_graph.md § Error Behaviour
"""

from __future__ import annotations

import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.graph.rag_query_graph import (
    build_rag_query_graph,
)
from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_table_schemas() -> list[TableSchema]:
    """Return sample table schemas simulating a post-ingestion ClickHouse state.

    Returns:
        A list with one TableSchema representing an export_revenue table.
    """
    return [
        TableSchema(
            table_name="export_revenue",
            columns=[
                ColumnInfo(column_name="year", column_type="Int32"),
                ColumnInfo(column_name="revenue", column_type="Decimal(18,4)"),
                ColumnInfo(column_name="source_reference", column_type="String"),
                ColumnInfo(column_name="ingestion_timestamp", column_type="DateTime"),
                ColumnInfo(column_name="content_hash", column_type="String"),
            ],
        )
    ]


def _make_query_assembler_llm(queries: list[str]) -> MagicMock:
    """Return a mock LLM for query assembly that yields the given SQL list.

    Args:
        queries: SQL strings the mock LLM should return.

    Returns:
        A MagicMock that simulates a structured-output LLM call.
    """
    structured_response = MagicMock()
    structured_response.sql_queries = queries
    structured_llm = MagicMock()
    structured_llm.ainvoke = AsyncMock(return_value=structured_response)

    table_selection_response = MagicMock()
    table_selection_response.selected_table_names = ["export_revenue"]
    table_selection_llm = MagicMock()
    table_selection_llm.ainvoke = AsyncMock(return_value=table_selection_response)

    llm = MagicMock()
    call_count = 0

    def structured_output_side_effect(schema: Any, **kwargs: Any) -> MagicMock:
        """Return different mocks for table selection vs query assembly calls."""
        # First call = table selection, second call = query assembly
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return table_selection_llm
        return structured_llm

    llm.with_structured_output = MagicMock(side_effect=structured_output_side_effect)
    return llm


# ---------------------------------------------------------------------------
# US4 Acceptance Scenario — question → CSV file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rag_query_graph_produces_csv_file(mock_clickhouse_client: MagicMock) -> None:
    """RAG graph returns a CSV file path for a valid question with data.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
    """
    with tempfile.TemporaryDirectory() as export_dir:
        query_rows = [{"year": 2023, "revenue": "100000.0000"}]

        with (
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".introspect_schema_node.get_all_table_schemas",
                new=AsyncMock(return_value=_make_table_schemas()),
            ),
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".execute_queries_node.execute_select_query",
                new=AsyncMock(return_value=query_rows),
            ),
        ):
            llm = _make_query_assembler_llm(
                ["SELECT year, revenue FROM export_revenue LIMIT 10000"]
            )
            graph = build_rag_query_graph(llm=llm, clickhouse_client=mock_clickhouse_client)
            result_state = await graph.ainvoke(
                {
                    "natural_language_question": "What were total export revenues by year?",
                    "export_row_limit": 10000,
                    "export_directory": export_dir,
                }
            )

        output = result_state["rag_query_output"]
        assert output["export_file_path"] is not None
        assert os.path.isfile(output["export_file_path"])
        assert output["row_count"] > 0
        assert len(output["sql_queries_used"]) > 0
        assert output["rationale"] is not None


@pytest.mark.asyncio
async def test_rag_query_graph_empty_result_returns_no_file(
    mock_clickhouse_client: MagicMock,
) -> None:
    """When queries return no rows, export_file_path is None and rationale explains.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
    """
    with tempfile.TemporaryDirectory() as export_dir:
        with (
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".introspect_schema_node.get_all_table_schemas",
                new=AsyncMock(return_value=_make_table_schemas()),
            ),
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".execute_queries_node.execute_select_query",
                new=AsyncMock(return_value=[]),
            ),
        ):
            llm = _make_query_assembler_llm(
                ["SELECT year, revenue FROM export_revenue WHERE year = 1900 LIMIT 10000"]
            )
            graph = build_rag_query_graph(llm=llm, clickhouse_client=mock_clickhouse_client)
            result_state = await graph.ainvoke(
                {
                    "natural_language_question": "Revenue in year 1900?",
                    "export_row_limit": 10000,
                    "export_directory": export_dir,
                }
            )

        output = result_state["rag_query_output"]
        assert output["export_file_path"] is None
        assert "No relevant data" in output["rationale"]


@pytest.mark.asyncio
async def test_rag_query_graph_truncation_sets_was_truncated(
    mock_clickhouse_client: MagicMock,
) -> None:
    """When results exceed export_row_limit, was_truncated is True in output.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
    """
    row_limit = 2
    # Return more rows than the limit to trigger truncation.
    excess_rows = [{"year": y, "revenue": "100.0000"} for y in range(row_limit + 3)]

    with tempfile.TemporaryDirectory() as export_dir:
        with (
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".introspect_schema_node.get_all_table_schemas",
                new=AsyncMock(return_value=_make_table_schemas()),
            ),
            patch(
                "latam_investment_research_agent.agents.analytics.nodes.rag"
                ".execute_queries_node.execute_select_query",
                new=AsyncMock(return_value=excess_rows),
            ),
        ):
            llm = _make_query_assembler_llm(
                ["SELECT year, revenue FROM export_revenue LIMIT 2"]
            )
            graph = build_rag_query_graph(llm=llm, clickhouse_client=mock_clickhouse_client)
            result_state = await graph.ainvoke(
                {
                    "natural_language_question": "What were revenues?",
                    "export_row_limit": row_limit,
                    "export_directory": export_dir,
                }
            )

        output = result_state["rag_query_output"]
        assert output["was_truncated"] is True
        assert output["row_count"] == row_limit
        assert "truncat" in output["rationale"].lower()


@pytest.mark.asyncio
async def test_rag_query_graph_no_tables_returns_graceful_error(
    mock_clickhouse_client: MagicMock,
) -> None:
    """When ClickHouse has no tables, graph routes to build_rag_response with error.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
    """
    with tempfile.TemporaryDirectory() as export_dir:
        with patch(
            "latam_investment_research_agent.agents.analytics.nodes.rag"
            ".introspect_schema_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ):
            llm = MagicMock()
            graph = build_rag_query_graph(llm=llm, clickhouse_client=mock_clickhouse_client)
            result_state = await graph.ainvoke(
                {
                    "natural_language_question": "Any question",
                    "export_row_limit": 10000,
                    "export_directory": export_dir,
                }
            )

        output = result_state["rag_query_output"]
        assert output["export_file_path"] is None
        assert output["rationale"] is not None
