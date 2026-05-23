"""Unit tests for ClickHouse SQL repair before execution."""

from __future__ import annotations

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnInfo,
    TableSchema,
)
from latam_investment_research_agent.agents.analytics.services.sql_query_repair import (
    repair_clickhouse_select,
)


def test_repair_strips_any_source_reference_without_group_by() -> None:
    """``any(source_reference)`` without GROUP BY becomes a plain column."""
    sql_query = (
        "SELECT any(source_reference) AS source_reference, region, category, rank "
        "FROM cooxup_brand_ranking_in_superhiper_guide_2025 "
        "WHERE region = 'Brazil' ORDER BY rank ASC LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query)
    assert "any(source_reference)" not in repaired.lower()
    assert "source_reference" in repaired.lower()
    assert "GROUP BY" not in repaired.upper()


def test_repair_extends_group_by_for_bare_select_columns() -> None:
    """Non-aggregated SELECT columns are added to GROUP BY (ClickHouse code 215)."""
    sql_query = (
        "SELECT any(source_reference) AS source_reference, terminal, ytd_value, "
        "market_share_percentage "
        "FROM ytd_values_and_market_share_by_terminal "
        "GROUP BY terminal "
        "ORDER BY market_share_percentage DESC LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query)
    assert "GROUP BY terminal, ytd_value, market_share_percentage" in repaired


def test_repair_adds_group_by_for_aggregate_without_group_by() -> None:
    """Aggregate queries missing GROUP BY receive grouping keys and ``any(source_reference)``."""
    sql_query = (
        "SELECT source_reference, year, SUM(bags) AS total_bags "
        "FROM average_coffee_prices_over_the_last_10_years LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query)
    assert "GROUP BY year" in repaired
    assert "any(source_reference)" in repaired.lower()


def test_repair_adds_group_by_for_multi_column_aggregate() -> None:
    """Every non-aggregate column is grouped when aggregates omit GROUP BY."""
    sql_query = (
        "SELECT source_reference, region, MIN(rank) AS best_rank "
        "FROM cooxup_brand_ranking_in_superhiper_guide_2025 "
        "WHERE region = 'Brazil' LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query)
    assert "GROUP BY region" in repaired
    assert "any(source_reference)" in repaired.lower()


def test_repair_adds_group_by_for_partial_aggregate_select() -> None:
    """Bare dimension columns in aggregate SELECT lists are grouped."""
    sql_query = (
        "SELECT category, SUM(rank) AS total_rank, any(source_reference) AS source_reference "
        "FROM cooxup_brand_ranking_in_superhiper_guide_2025 LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query)
    assert "GROUP BY category" in repaired


def test_repair_drops_unknown_group_by_column_using_schema() -> None:
    """Invented columns such as ``month`` are removed when schema is provided."""
    schema = TableSchema(
        table_name="coffee_receipt_and_shipment_data",
        columns=[
            ColumnInfo(column_name="bags_shipped", column_type="Int32"),
            ColumnInfo(column_name="bags_received", column_type="Int32"),
            ColumnInfo(column_name="source_reference", column_type="String"),
        ],
    )
    sql_query = (
        "SELECT any(source_reference) AS source_reference, month, "
        "sum(bags_shipped) AS total_bags_shipped "
        "FROM coffee_receipt_and_shipment_data "
        "GROUP BY month ORDER BY total_bags_shipped DESC LIMIT 10000"
    )
    repaired = repair_clickhouse_select(sql_query, schema)
    assert "month" not in repaired.lower()
