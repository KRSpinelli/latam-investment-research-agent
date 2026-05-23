"""Template ClickHouse SELECT queries for broad analytical exploration."""

from __future__ import annotations

import re

from latam_investment_research_agent.agents.analytics.constants import MANDATORY_AUDIT_COLUMNS
from latam_investment_research_agent.agents.analytics.models.domain import ColumnInfo, TableSchema

_SOURCE_REFERENCE_COLUMN = MANDATORY_AUDIT_COLUMNS[0]
_NUMERIC_TYPE_PATTERN = re.compile(r"int|float|decimal|uint", re.IGNORECASE)
_DIMENSION_PATTERN = re.compile(
    r"year|period|date|month|quarter|terminal|port|region|category|name|type|country|city|label",
    re.IGNORECASE,
)
_TABLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_numeric_column(column: ColumnInfo) -> bool:
    """Return True when a ClickHouse column type is numeric.

    Args:
        column: Column metadata from DESCRIBE TABLE.

    Returns:
        True for integer, float, and decimal types.
    """
    return bool(_NUMERIC_TYPE_PATTERN.search(column.column_type))


def _is_dimension_column(column: ColumnInfo) -> bool:
    """Return True when a column is suitable for GROUP BY breakdowns.

    Args:
        column: Column metadata from DESCRIBE TABLE.

    Returns:
        True for string-like dimensions and date/year columns.
    """
    if column.column_name in MANDATORY_AUDIT_COLUMNS:
        return False
    if _is_numeric_column(column):
        return bool(_DIMENSION_PATTERN.search(column.column_name))
    return column.column_type.lower().startswith("string")


def build_exploratory_queries(
    schemas: list[TableSchema],
    *,
    row_limit: int = 10_000,
    max_queries_per_table: int = 4,
) -> list[str]:
    """Build safe, schema-aware SELECT queries without an LLM.

    Args:
        schemas: ClickHouse table schemas to explore.
        row_limit: LIMIT for each generated query.
        max_queries_per_table: Cap queries per table to control volume.

    Returns:
        List of DISTINCT SELECT statements.
    """
    queries: list[str] = []
    seen: set[str] = set()

    def add_query(sql_query: str) -> None:
        normalized = sql_query.strip().rstrip(";")
        if normalized and normalized not in seen:
            seen.add(normalized)
            queries.append(normalized)

    for schema in schemas:
        table_name = schema.table_name.strip().lower()
        if not _TABLE_NAME_PATTERN.match(table_name):
            continue

        per_table = 0

        add_query(
            f"SELECT {_SOURCE_REFERENCE_COLUMN}, * EXCEPT ({_SOURCE_REFERENCE_COLUMN}) "
            f"FROM {table_name} "
            f"ORDER BY ingestion_timestamp DESC "
            f"LIMIT {row_limit}"
        )
        per_table += 1

        numeric_columns = [
            column.column_name
            for column in schema.columns
            if _is_numeric_column(column)
            and column.column_name not in MANDATORY_AUDIT_COLUMNS
        ]
        dimension_columns = [
            column.column_name for column in schema.columns if _is_dimension_column(column)
        ]

        for numeric_column in numeric_columns[:3]:
            if per_table >= max_queries_per_table:
                break
            add_query(
                f"SELECT {_SOURCE_REFERENCE_COLUMN}, {numeric_column} "
                f"FROM {table_name} "
                f"WHERE {numeric_column} IS NOT NULL "
                f"ORDER BY {numeric_column} DESC "
                f"LIMIT {row_limit}"
            )
            per_table += 1

        for dimension_column in dimension_columns[:2]:
            if per_table >= max_queries_per_table:
                break
            if not numeric_columns:
                continue
            value_column = numeric_columns[0]
            add_query(
                f"SELECT {dimension_column}, "
                f"SUM({value_column}) AS total_{value_column}, "
                f"any({_SOURCE_REFERENCE_COLUMN}) AS {_SOURCE_REFERENCE_COLUMN} "
                f"FROM {table_name} "
                f"GROUP BY {dimension_column} "
                f"ORDER BY total_{value_column} DESC "
                f"LIMIT {row_limit}"
            )
            per_table += 1

    return queries
