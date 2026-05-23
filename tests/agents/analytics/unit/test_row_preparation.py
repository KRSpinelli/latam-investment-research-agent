"""Unit tests for row normalization and coercion before ClickHouse insert."""

from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition
from latam_investment_research_agent.agents.analytics.repositories.row_preparation import (
    coerce_cell_value,
    merge_schema_with_row_keys,
    normalize_column_key,
    normalize_rows,
)


def test_normalize_column_key_prefixes_leading_digit() -> None:
    """Year-style column headers become valid identifiers."""
    assert normalize_column_key("2023") == "col_2023"
    assert normalize_column_key("2025_total") == "col_2025_total"


def test_merge_schema_with_row_keys_adds_missing_columns() -> None:
    """Row keys not in proposed_schema are added as String columns."""
    proposed_schema = [
        ColumnDefinition(
            column_name="metric",
            clickhouse_type="String",
            description="Metric label",
        ),
    ]
    rows = [{"metric": "Revenue", "col_2023": "100", "col_2024": "120"}]

    merged = merge_schema_with_row_keys(proposed_schema, rows)

    column_names = {column.column_name for column in merged}
    assert column_names == {"metric", "col_2023", "col_2024"}
    assert next(column for column in merged if column.column_name == "col_2023").clickhouse_type == "String"


def test_coerce_cell_value_parses_percentage_for_numeric_types() -> None:
    """Percentages coerce to numbers for numeric ClickHouse types."""
    assert coerce_cell_value("74.64%", "Float64") == "74.64"
    assert coerce_cell_value("74.64%", "UInt32") == 74


def test_coerce_cell_value_parses_brazilian_decimal() -> None:
    """Locale-formatted decimals coerce to ClickHouse decimal strings."""
    assert coerce_cell_value("1.234,56", "Decimal(18,4)") == "1234.56"


def test_coerce_cell_value_preserves_text_for_string_columns() -> None:
    """Non-numeric labels remain strings."""
    assert coerce_cell_value("June 9, 2025", "String") == "June 9, 2025"
    assert coerce_cell_value("lower", "String") == "lower"


def test_normalize_rows_renames_year_columns() -> None:
    """Row dict keys are normalized consistently."""
    rows = normalize_rows([{"2023": "10", "2024": "20"}])
    assert rows == [{"col_2023": "10", "col_2024": "20"}]
