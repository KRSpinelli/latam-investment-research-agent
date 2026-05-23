"""Unit tests for the LLM-based table routing service.

Uses a mock BaseChatModel — no live LLM calls.
Run and confirm FAILING before implementing services/table_router.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.constants import (
    CREATE_NEW_TABLE_SENTINEL,
)
from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnDefinition,
    ColumnInfo,
    ExtractedDataset,
    RoutingDecision,
    TableSchema,
)
from latam_investment_research_agent.agents.analytics.services.table_router import (
    route_dataset,
)


def _make_dataset(name: str = "Annual Revenue") -> ExtractedDataset:
    """Build a minimal ExtractedDataset for testing.

    Args:
        name: Dataset name.

    Returns:
        An ExtractedDataset with one column and one row.
    """
    return ExtractedDataset(
        dataset_name=name,
        context_labels=["Financial Summary"],
        column_names=["year", "revenue_brl"],
        rows=[{"year": 2023, "revenue_brl": "1000000.00"}],
    )


def _make_existing_schemas() -> list[TableSchema]:
    """Build a list of existing TableSchema objects for testing.

    Returns:
        A list with one TableSchema representing an existing annual revenue table.
    """
    return [
        TableSchema(
            table_name="annual_revenue",
            columns=[
                ColumnInfo(column_name="source_reference", column_type="String"),
                ColumnInfo(column_name="ingestion_timestamp", column_type="DateTime64(3, 'UTC')"),
                ColumnInfo(column_name="content_hash", column_type="String"),
                ColumnInfo(column_name="year", column_type="UInt16"),
                ColumnInfo(column_name="revenue_brl", column_type="Decimal(18,4)"),
            ],
        )
    ]


@pytest.mark.asyncio
async def test_route_dataset_returns_routing_decision(
    mock_llm_provider: MagicMock,
) -> None:
    """route_dataset returns a RoutingDecision object."""
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=RoutingDecision(
            target_table_name="annual_revenue",
            routing_action="append",
            rationale="Matches existing annual revenue table.",
            proposed_schema=None,
        )
    )

    result = await route_dataset(_make_dataset(), _make_existing_schemas(), mock_llm_provider)

    assert isinstance(result, RoutingDecision)
    assert result.routing_action == "append"
    assert result.target_table_name == "annual_revenue"


@pytest.mark.asyncio
async def test_route_dataset_returns_create_new_when_no_match(
    mock_llm_provider: MagicMock,
) -> None:
    """route_dataset returns routing_action='create' with the sentinel when no table matches."""
    proposed_schema = [
        ColumnDefinition(
            column_name="export_volume_tonnes",
            clickhouse_type="Decimal(18,4)",
            description="Export volume in tonnes",
        )
    ]
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=RoutingDecision(
            target_table_name=CREATE_NEW_TABLE_SENTINEL,
            routing_action="create",
            rationale="No matching table found.",
            proposed_schema=proposed_schema,
        )
    )

    result = await route_dataset(_make_dataset("Coffee Exports"), [], mock_llm_provider)

    assert result.routing_action == "create"
    assert result.target_table_name == CREATE_NEW_TABLE_SENTINEL
    assert result.proposed_schema is not None


@pytest.mark.asyncio
async def test_route_dataset_raises_if_proposed_schema_contains_audit_columns(
    mock_llm_provider: MagicMock,
) -> None:
    """route_dataset raises ValueError if proposed_schema includes audit column names."""
    invalid_proposed_schema = [
        ColumnDefinition(
            column_name="source_reference",  # reserved audit column
            clickhouse_type="String",
            description="Should not be here",
        )
    ]
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=RoutingDecision(
            target_table_name=CREATE_NEW_TABLE_SENTINEL,
            routing_action="create",
            rationale="Creating new table.",
            proposed_schema=invalid_proposed_schema,
        )
    )

    with pytest.raises(ValueError, match="source_reference"):
        await route_dataset(_make_dataset(), [], mock_llm_provider)


@pytest.mark.asyncio
async def test_route_dataset_uses_create_new_table_sentinel_constant(
    mock_llm_provider: MagicMock,
) -> None:
    """route_dataset uses the CREATE_NEW_TABLE_SENTINEL constant, not a literal string."""
    proposed_schema = [
        ColumnDefinition(
            column_name="price_usd", clickhouse_type="Decimal(18,4)", description="Price"
        )
    ]
    mock_decision = RoutingDecision(
        target_table_name=CREATE_NEW_TABLE_SENTINEL,
        routing_action="create",
        rationale="New dataset.",
        proposed_schema=proposed_schema,
    )
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=mock_decision
    )

    result = await route_dataset(_make_dataset(), [], mock_llm_provider)
    assert result.target_table_name == CREATE_NEW_TABLE_SENTINEL
