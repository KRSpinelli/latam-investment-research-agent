"""Unit tests for the query assembler service.

Tests that assemble_queries returns valid SELECT-only statements and
silently discards any non-SELECT queries returned by the LLM.

See: plan.md § RAG Query: SELECT-Only Guard
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)
from latam_investment_research_agent.agents.analytics.services.query_assembler import (
    assemble_queries,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_schemas() -> list[TableSchema]:
    """Return a minimal list of TableSchema objects for testing.

    Returns:
        A list containing one TableSchema with two columns.
    """
    return [
        TableSchema(
            table_name="export_revenue",
            columns=[
                ColumnInfo(column_name="year", column_type="Int32"),
                ColumnInfo(column_name="revenue", column_type="Decimal(18,4)"),
                ColumnInfo(column_name="source_reference", column_type="String"),
            ],
        )
    ]


def _make_llm_returning(queries: list[str]) -> MagicMock:
    """Return a mock LLM whose structured output yields the given query list.

    Args:
        queries: SQL strings the mock LLM should return.

    Returns:
        A MagicMock configured to return a Pydantic-like object with
        ``sql_queries`` attribute set to ``queries``.
    """
    structured_response = MagicMock()
    structured_response.sql_queries = queries
    structured_llm = MagicMock()
    structured_llm.ainvoke = AsyncMock(return_value=structured_response)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured_llm)
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assemble_queries_returns_nonempty_list(sample_schemas: list[TableSchema]) -> None:
    """assemble_queries returns at least one query for a valid question.

    Args:
        sample_schemas: Fixture providing a sample list of table schemas.
    """
    llm = _make_llm_returning(["SELECT year, revenue FROM export_revenue LIMIT 10000"])
    result = await assemble_queries(
        question="What were total export revenues by year?",
        selected_schemas=sample_schemas,
        llm=llm,
    )
    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_assemble_queries_all_results_start_with_select(
    sample_schemas: list[TableSchema],
) -> None:
    """Every query returned by assemble_queries starts with SELECT.

    Args:
        sample_schemas: Fixture providing a sample list of table schemas.
    """
    llm = _make_llm_returning([
        "SELECT year, revenue FROM export_revenue LIMIT 10000",
        "SELECT source_reference FROM export_revenue LIMIT 10000",
    ])
    result = await assemble_queries(
        question="What were total export revenues by year?",
        selected_schemas=sample_schemas,
        llm=llm,
    )
    for query in result:
        assert query.strip().upper().startswith("SELECT"), (
            f"Non-SELECT query returned: {query!r}"
        )


@pytest.mark.asyncio
async def test_assemble_queries_discards_non_select_queries(
    sample_schemas: list[TableSchema],
) -> None:
    """Non-SELECT queries from the LLM are silently discarded.

    If the LLM returns a mix of SELECT and non-SELECT queries, only SELECT
    queries must appear in the returned list.

    Args:
        sample_schemas: Fixture providing a sample list of table schemas.
    """
    llm = _make_llm_returning([
        "SELECT year, revenue FROM export_revenue LIMIT 10000",
        "DROP TABLE export_revenue",
        "INSERT INTO export_revenue VALUES (2024, 999)",
        "SELECT source_reference FROM export_revenue LIMIT 10000",
    ])
    result = await assemble_queries(
        question="What were total export revenues by year?",
        selected_schemas=sample_schemas,
        llm=llm,
    )
    assert len(result) == 2
    for query in result:
        assert query.strip().upper().startswith("SELECT")


@pytest.mark.asyncio
async def test_assemble_queries_all_non_select_returns_empty_list(
    sample_schemas: list[TableSchema],
) -> None:
    """If the LLM returns only non-SELECT queries, the result is an empty list.

    Args:
        sample_schemas: Fixture providing a sample list of table schemas.
    """
    llm = _make_llm_returning([
        "DROP TABLE export_revenue",
        "DELETE FROM export_revenue WHERE year < 2000",
    ])
    result = await assemble_queries(
        question="Delete old data",
        selected_schemas=sample_schemas,
        llm=llm,
    )
    assert result == []


@pytest.mark.asyncio
async def test_assemble_queries_select_check_is_case_insensitive(
    sample_schemas: list[TableSchema],
) -> None:
    """SELECT validation is case-insensitive (allows 'select', 'Select', etc).

    Args:
        sample_schemas: Fixture providing a sample list of table schemas.
    """
    llm = _make_llm_returning(["select year from export_revenue limit 10000"])
    result = await assemble_queries(
        question="Get years",
        selected_schemas=sample_schemas,
        llm=llm,
    )
    assert len(result) == 1
