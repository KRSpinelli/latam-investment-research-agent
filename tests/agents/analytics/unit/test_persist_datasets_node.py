"""Unit tests for the parallel persist_datasets ingestion node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnDefinition,
    ExtractedDataset,
    RoutingDecision,
)
from latam_investment_research_agent.agents.analytics.nodes.ingestion.persist_datasets_node import (
    persist_datasets_node,
)


def _make_dataset(name: str) -> ExtractedDataset:
    """Return a minimal extracted dataset for testing.

    Args:
        name: Dataset name.

    Returns:
        An ``ExtractedDataset`` with one sample row.
    """
    return ExtractedDataset(
        dataset_name=name,
        context_labels=["test"],
        column_names=["year", "revenue"],
        rows=[{"year": 2023, "revenue": 100000}],
    )


def _make_routing_decision(action: str = "create") -> RoutingDecision:
    """Return a routing decision for testing.

    Args:
        action: Either ``"create"`` or ``"append"``.

    Returns:
        A ``RoutingDecision`` with a minimal proposed schema.
    """
    return RoutingDecision(
        target_table_name="existing_table" if action == "append" else "__create_new__",
        routing_action=action,  # type: ignore[arg-type]
        rationale="test",
        proposed_schema=[
            ColumnDefinition(
                column_name="year",
                clickhouse_type="Int32",
                description="Year",
            ),
            ColumnDefinition(
                column_name="revenue",
                clickhouse_type="Decimal(18,4)",
                description="Revenue",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_persist_datasets_empty_list() -> None:
    """No datasets returns empty results and failures."""
    result = await persist_datasets_node(
        {"source_reference": "https://example.com/doc.pdf", "extracted_datasets": []},
        llm=MagicMock(),
        clickhouse_client=MagicMock(),
    )
    assert result["ingestion_results"] == []
    assert result["ingestion_failures"] == []


@pytest.mark.asyncio
async def test_persist_datasets_routes_all_datasets_in_parallel() -> None:
    """All datasets are routed concurrently via asyncio.gather."""
    datasets = [_make_dataset("first"), _make_dataset("second")]
    routing_decision = _make_routing_decision("create")

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.route_dataset",
            new=AsyncMock(return_value=routing_decision),
        ) as route_mock,
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.create_tables_parallel",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.insert_rows_deduplicated",
            new=AsyncMock(return_value=1),
        ),
    ):
        result = await persist_datasets_node(
            {"source_reference": "https://example.com/doc.pdf", "extracted_datasets": datasets},
            llm=MagicMock(),
            clickhouse_client=MagicMock(),
        )

    assert route_mock.await_count == 2
    assert len(result["ingestion_results"]) == 2
    assert result["ingestion_failures"] == []


@pytest.mark.asyncio
async def test_persist_datasets_captures_routing_failure() -> None:
    """A routing exception becomes a DatasetIngestionFailure without stopping others."""
    datasets = [_make_dataset("good"), _make_dataset("bad")]
    routing_decision = _make_routing_decision("create")

    async def flaky_route(dataset, schemas, llm):
        if dataset.dataset_name == "bad":
            raise RuntimeError("routing failed")
        return routing_decision

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.route_dataset",
            new=AsyncMock(side_effect=flaky_route),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.create_tables_parallel",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.insert_rows_deduplicated",
            new=AsyncMock(return_value=1),
        ),
    ):
        result = await persist_datasets_node(
            {"source_reference": "https://example.com/doc.pdf", "extracted_datasets": datasets},
            llm=MagicMock(),
            clickhouse_client=MagicMock(),
        )

    assert len(result["ingestion_results"]) == 1
    assert len(result["ingestion_failures"]) == 1
    assert result["ingestion_failures"][0].dataset_name == "bad"


@pytest.mark.asyncio
async def test_persist_datasets_captures_write_failure() -> None:
    """A write exception becomes a DatasetIngestionFailure without stopping others."""
    datasets = [_make_dataset("good"), _make_dataset("bad")]
    routing_decision = _make_routing_decision("create")
    call_count = 0

    async def flaky_insert(client, table_name, rows, source_reference):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("write failed")
        return 1

    with (
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.get_all_table_schemas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.route_dataset",
            new=AsyncMock(return_value=routing_decision),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.create_tables_parallel",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "latam_investment_research_agent.agents.analytics.nodes.ingestion"
            ".persist_datasets_node.insert_rows_deduplicated",
            new=AsyncMock(side_effect=flaky_insert),
        ),
    ):
        result = await persist_datasets_node(
            {"source_reference": "https://example.com/doc.pdf", "extracted_datasets": datasets},
            llm=MagicMock(),
            clickhouse_client=MagicMock(),
        )

    assert len(result["ingestion_results"]) == 1
    assert len(result["ingestion_failures"]) == 1
    assert "write failed" in result["ingestion_failures"][0].error_detail
