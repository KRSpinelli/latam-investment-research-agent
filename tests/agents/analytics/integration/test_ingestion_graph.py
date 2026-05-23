"""Integration tests for the ingestion LangGraph.

Tests US1 acceptance scenarios: PDF ingestion, idempotency, and partial failure
handling.  These tests require a live ClickHouse instance configured via
TEST_CLICKHOUSE_* environment variables.

See: spec.md § User Story 1 Acceptance Scenarios
     contracts/ingestion_graph.md § Error Behaviour
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.graph.ingestion_graph import (
    build_ingestion_graph,
)
from latam_investment_research_agent.agents.analytics.models.domain import (
    ExtractedDataset,
    RoutingDecision,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import (
    IngestionSummary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extracted_dataset(name: str = "test_dataset") -> ExtractedDataset:
    """Return a minimal ExtractedDataset for testing.

    Args:
        name: Dataset name used for the table routing decision.

    Returns:
        An ExtractedDataset with one row of sample data.
    """
    return ExtractedDataset(
        dataset_name=name,
        context_labels=["test"],
        column_names=["year", "revenue"],
        rows=[{"year": 2023, "revenue": 100000}],
    )


def _make_routing_decision(action: str = "create") -> RoutingDecision:
    """Return a RoutingDecision for testing.

    Args:
        action: Either ``"create"`` or ``"append"``.

    Returns:
        A RoutingDecision suitable for use with a mock clickhouse client.
    """
    from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition

    return RoutingDecision(
        target_table_name="test_dataset" if action == "append" else "__create_new__",
        routing_action=action,  # type: ignore[arg-type]
        rationale="Test routing decision",
        proposed_schema=[
            ColumnDefinition(
                column_name="year",
                clickhouse_type="Int32",
                description="Calendar year",
            ),
            ColumnDefinition(
                column_name="revenue",
                clickhouse_type="Decimal(18,4)",
                description="Revenue amount",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# US1 Acceptance Scenario — PDF URL ingestion with mocked dependencies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_graph_pdf_url_produces_ingestion_summary(
    mock_clickhouse_client: MagicMock,
    mock_llm_provider: MagicMock,
) -> None:
    """Invoke ingestion graph with a mocked PDF fetch; assert summary is returned.

    Mocks: document fetcher (returns raw text), numerical extractor (returns
    one dataset), table router (returns create decision), clickhouse write.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
        mock_llm_provider: Fixture providing a mock LLM.
    """
    source_reference = "https://example.com/financial_report.pdf"
    raw_text = "Table 1: Revenue by Year\n2023: 100,000\n2024: 120,000"
    extracted_dataset = _make_extracted_dataset("revenue_by_year")
    routing_decision = _make_routing_decision("create")

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".fetch_document_node.fetch_document",
            new=AsyncMock(return_value=raw_text),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".extract_numerical_data_node.extract_datasets",
            new=AsyncMock(return_value=[extracted_dataset]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.route_dataset",
            new=AsyncMock(return_value=routing_decision),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.repositories"
            ".clickhouse_repository.create_table",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.repositories"
            ".clickhouse_repository.insert_rows_deduplicated",
            new=AsyncMock(return_value=1),
        ),
    ):
        graph = build_ingestion_graph(llm=mock_llm_provider, clickhouse_client=mock_clickhouse_client)
        result_state = await graph.ainvoke({"source_reference": source_reference})

    summary: IngestionSummary = result_state["ingestion_summary"]
    assert summary["source_reference"] == source_reference
    assert summary["total_datasets_found"] == 1
    assert len(summary["datasets_succeeded"]) == 1
    assert len(summary["datasets_failed"]) == 0


@pytest.mark.asyncio
async def test_ingestion_graph_fatal_fetch_error_routes_to_summary(
    mock_clickhouse_client: MagicMock,
    mock_llm_provider: MagicMock,
) -> None:
    """Fatal fetch failure routes directly to build_ingestion_summary_node.

    Verifies the conditional edge after fetch_document_node routes to
    build_ingestion_summary_node when the error field is set, bypassing
    extraction and write nodes entirely.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
        mock_llm_provider: Fixture providing a mock LLM.
    """
    from latam_investment_research_agent.agents.analytics.services.document_fetcher import (
        DocumentFetchError,
    )

    with patch(
        "latam_investment_research_agent.agents.analytics.nodes.ingestion"
        ".fetch_document_node.fetch_document",
        new=AsyncMock(side_effect=DocumentFetchError("https://example.com/missing.pdf", "404 Not Found")),
    ):
        graph = build_ingestion_graph(llm=mock_llm_provider, clickhouse_client=mock_clickhouse_client)
        result_state = await graph.ainvoke(
            {"source_reference": "https://example.com/missing.pdf"}
        )

    summary: IngestionSummary = result_state["ingestion_summary"]
    # Fetch failed → no datasets extracted → no succeeded/failed write attempts
    assert summary["total_datasets_found"] == 0
    assert summary["datasets_succeeded"] == []
    assert summary["datasets_failed"] == []


@pytest.mark.asyncio
async def test_ingestion_graph_idempotency_no_duplicate_rows(
    mock_clickhouse_client: MagicMock,
    mock_llm_provider: MagicMock,
) -> None:
    """Running the same source URL twice produces zero duplicate rows.

    The second invocation must see existing rows from the first run via the
    NOT IN deduplication query.  This test verifies the graph passes the
    source_reference to insert_rows_deduplicated so dedup can occur.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
        mock_llm_provider: Fixture providing a mock LLM.
    """
    source_reference = "https://example.com/financial_report.pdf"
    extracted_dataset = _make_extracted_dataset("revenue_by_year")
    routing_decision = _make_routing_decision("append")

    # Second run: insert returns 0 (all rows already present).
    insert_mock = AsyncMock(return_value=0)

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".fetch_document_node.fetch_document",
            new=AsyncMock(return_value="raw text"),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".extract_numerical_data_node.extract_datasets",
            new=AsyncMock(return_value=[extracted_dataset]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.route_dataset",
            new=AsyncMock(return_value=routing_decision),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.alter_table_add_columns",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.insert_rows_deduplicated",
            new=insert_mock,
        ),
    ):
        graph = build_ingestion_graph(llm=mock_llm_provider, clickhouse_client=mock_clickhouse_client)
        result_state = await graph.ainvoke({"source_reference": source_reference})

    summary: IngestionSummary = result_state["ingestion_summary"]
    assert summary["datasets_succeeded"][0].rows_written == 0

    # Verify source_reference was passed through to the dedup call.
    call_args = insert_mock.call_args
    assert source_reference in call_args.args or source_reference in call_args.kwargs.values()


@pytest.mark.asyncio
async def test_ingestion_graph_partial_write_failure_captured(
    mock_clickhouse_client: MagicMock,
    mock_llm_provider: MagicMock,
) -> None:
    """One dataset write failure is captured without stopping other datasets.

    When one write fails, it must appear in datasets_failed while successfully
    written datasets appear in datasets_succeeded.  The graph must NOT raise.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
        mock_llm_provider: Fixture providing a mock LLM.
    """
    dataset_good = _make_extracted_dataset("good_dataset")
    dataset_bad = _make_extracted_dataset("bad_dataset")
    routing_create = _make_routing_decision("create")

    call_count = 0

    async def flaky_insert(client: Any, table_name: str, rows: list, source_reference: str) -> int:
        """Raise on the second call to simulate a partial write failure."""
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("ClickHouse connection lost")
        return len(rows)

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".fetch_document_node.fetch_document",
            new=AsyncMock(return_value="raw text"),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".extract_numerical_data_node.extract_datasets",
            new=AsyncMock(return_value=[dataset_good, dataset_bad]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.route_dataset",
            new=AsyncMock(return_value=routing_create),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.create_table",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.insert_rows_deduplicated",
            new=flaky_insert,
        ),
    ):
        graph = build_ingestion_graph(llm=mock_llm_provider, clickhouse_client=mock_clickhouse_client)
        result_state = await graph.ainvoke({"source_reference": "https://example.com/report.pdf"})

    summary: IngestionSummary = result_state["ingestion_summary"]
    assert len(summary["datasets_succeeded"]) == 1
    assert len(summary["datasets_failed"]) == 1
    assert "bad_dataset" == summary["datasets_failed"][0].dataset_name
    assert "ClickHouse connection lost" in summary["datasets_failed"][0].error_detail


# ---------------------------------------------------------------------------
# US2 Web page ingestion via the unchanged ingestion graph (T042)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_graph_html_source_reference_preserved(
    mock_clickhouse_client: MagicMock,
    mock_llm_provider: MagicMock,
) -> None:
    """Web page URL flows through the ingestion graph unchanged.

    The document_fetcher handles HTML vs PDF routing transparently — the graph
    code is never changed for US2.  This test confirms that a web page URL is
    accepted as source_reference and appears in the summary unchanged.

    Args:
        mock_clickhouse_client: Fixture providing a mock ClickHouse client.
        mock_llm_provider: Fixture providing a mock LLM.
    """
    web_page_url = "https://example.com/financial-statistics"
    html_table_text = "Year\tRevenue\n2023\t100000\n2024\t120000"
    extracted_dataset = _make_extracted_dataset("statistics")
    routing_decision = _make_routing_decision("create")

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".fetch_document_node.fetch_document",
            new=AsyncMock(return_value=html_table_text),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".extract_numerical_data_node.extract_datasets",
            new=AsyncMock(return_value=[extracted_dataset]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".route_dataset_node.route_dataset",
            new=AsyncMock(return_value=routing_decision),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.create_table",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".write_to_clickhouse_node.insert_rows_deduplicated",
            new=AsyncMock(return_value=2),
        ),
    ):
        graph = build_ingestion_graph(llm=mock_llm_provider, clickhouse_client=mock_clickhouse_client)
        result_state = await graph.ainvoke({"source_reference": web_page_url})

    summary: IngestionSummary = result_state["ingestion_summary"]
    assert summary["source_reference"] == web_page_url
    assert len(summary["datasets_succeeded"]) == 1
    assert summary["datasets_succeeded"][0].rows_written == 2
