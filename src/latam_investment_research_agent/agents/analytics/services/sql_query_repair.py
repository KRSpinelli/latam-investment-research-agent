"""Repair common ClickHouse SELECT mistakes from LLM-generated SQL."""

from __future__ import annotations

import logging
import re

from latam_investment_research_agent.agents.analytics.constants import MANDATORY_AUDIT_COLUMNS
from latam_investment_research_agent.agents.analytics.models.domain import TableSchema

logger = logging.getLogger(__name__)

_SOURCE_REFERENCE_COLUMN = MANDATORY_AUDIT_COLUMNS[0]
_AGGREGATE_FUNCTION_PATTERN = re.compile(
    r"\b(sum|count|avg|min|max|any|groupArray|uniq)\s*\(",
    re.IGNORECASE,
)
_FROM_TABLE_PATTERN = re.compile(r"(?i)\s+from\s+([a-z][a-z0-9_]*)")
_GROUP_BY_PATTERN = re.compile(r"(?i)\bgroup\s+by\b")
_ORDER_OR_LIMIT_PATTERN = re.compile(r"(?i)\b(order\s+by|having|limit)\b")


def extract_table_name(sql_query: str) -> str | None:
    """Extract the primary table name from a SELECT statement.

    Args:
        sql_query: SQL query string.

    Returns:
        Lowercase table name or None.
    """
    match = _FROM_TABLE_PATTERN.search(sql_query)
    if match is None:
        return None
    return match.group(1).lower()


def _split_select_list(select_list: str) -> list[str]:
    """Split a SELECT or GROUP BY column list on top-level commas.

    Args:
        select_list: Comma-separated SQL expressions.

    Returns:
        List of expression strings.
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for character in select_list:
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        if character == "," and depth == 0:
            expression = "".join(current).strip()
            if expression:
                parts.append(expression)
            current = []
            continue
        current.append(character)
    expression = "".join(current).strip()
    if expression:
        parts.append(expression)
    return parts


def _expression_output_name(expression: str) -> str:
    """Return the output column name for a SELECT expression.

    Args:
        expression: Single SELECT list expression.

    Returns:
        Alias or trailing identifier name.
    """
    alias_match = re.search(r"(?i)\bas\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", expression.strip())
    if alias_match:
        return alias_match.group(1)
    identifier_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*$", expression.strip())
    if identifier_match:
        return identifier_match.group(1)
    return expression.strip()


def _is_aggregate_expression(expression: str) -> bool:
    """Return True when a SELECT expression uses an aggregate function.

    Args:
        expression: SELECT list expression.

    Returns:
        True if the expression contains SUM/COUNT/any/etc.
    """
    return bool(_AGGREGATE_FUNCTION_PATTERN.search(expression))


def _remove_invalid_any_without_group_by(sql_query: str) -> str:
    """Replace ``any(source_reference)`` with plain ``source_reference`` when no GROUP BY.

    Args:
        sql_query: SQL query string.

    Returns:
        Repaired query string.
    """
    if _GROUP_BY_PATTERN.search(sql_query):
        return sql_query
    repaired = re.sub(
        r"(?i)\bany\s*\(\s*source_reference\s*\)\s+as\s+source_reference",
        "source_reference",
        sql_query,
    )
    return re.sub(
        r"(?i)\bany\s*\(\s*source_reference\s*\)",
        "source_reference",
        repaired,
    )


def _extend_group_by_for_bare_select_columns(sql_query: str) -> str:
    """Add missing non-aggregate SELECT columns to GROUP BY (ClickHouse code 215).

    Args:
        sql_query: SQL query containing GROUP BY.

    Returns:
        Query with a complete GROUP BY clause.
    """
    group_by_match = _GROUP_BY_PATTERN.search(sql_query)
    from_match = _FROM_TABLE_PATTERN.search(sql_query)
    if group_by_match is None or from_match is None:
        return sql_query

    select_list = sql_query[: from_match.start()]
    select_list = re.sub(r"(?is)^\s*select\s+", "", select_list).strip()
    if not select_list or select_list == "*":
        return sql_query

    tail = sql_query[group_by_match.end() :]
    tail_boundary = _ORDER_OR_LIMIT_PATTERN.search(tail)
    group_by_list = tail[: tail_boundary.start()] if tail_boundary else tail
    suffix = tail[tail_boundary.start() :] if tail_boundary else ""

    group_by_columns = [
        _expression_output_name(expression)
        for expression in _split_select_list(group_by_list)
    ]
    required_columns: list[str] = []
    for expression in _split_select_list(select_list):
        if _is_aggregate_expression(expression):
            continue
        column_name = _expression_output_name(expression)
        if column_name.lower() == _SOURCE_REFERENCE_COLUMN:
            continue
        required_columns.append(column_name)

    merged_group_by: list[str] = []
    for column_name in group_by_columns + required_columns:
        if column_name and column_name not in merged_group_by:
            merged_group_by.append(column_name)

    if merged_group_by == group_by_columns:
        return sql_query

    new_group_by_clause = ", ".join(merged_group_by)
    logger.debug(
        "Extended GROUP BY with columns: %s",
        ", ".join(column for column in required_columns if column not in group_by_columns),
    )
    return (
        f"{sql_query[: group_by_match.start()]}GROUP BY {new_group_by_clause}{suffix}"
    )


def _filter_unknown_columns(sql_query: str, schema: TableSchema) -> str:
    """Drop SELECT/GROUP BY references to columns that are not in the table schema.

    Args:
        sql_query: SQL query string.
        schema: Table schema for the query's FROM table.

    Returns:
        Query with unknown identifiers removed or simplified to a safe snapshot.
    """
    valid_columns = {column.column_name.lower() for column in schema.columns}
    valid_columns.update(column.lower() for column in MANDATORY_AUDIT_COLUMNS)

    from_match = _FROM_TABLE_PATTERN.search(sql_query)
    if from_match is None:
        return sql_query

    select_list = sql_query[: from_match.start()]
    select_list = re.sub(r"(?is)^\s*select\s+", "", select_list).strip()
    if select_list == "*":
        return sql_query

    kept_expressions: list[str] = []
    for expression in _split_select_list(select_list):
        output_name = _expression_output_name(expression).lower()
        referenced = {match.lower() for match in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expression)}
        if output_name in valid_columns or referenced.intersection(valid_columns):
            kept_expressions.append(expression)

    if not kept_expressions:
        table_name = schema.table_name
        return (
            f"SELECT {_SOURCE_REFERENCE_COLUMN}, * EXCEPT ({_SOURCE_REFERENCE_COLUMN}) "
            f"FROM {table_name} LIMIT 10000"
        )

    rebuilt_select = f"SELECT {', '.join(kept_expressions)}"
    remainder = sql_query[from_match.start() :]

    group_by_match = _GROUP_BY_PATTERN.search(remainder)
    if group_by_match is None:
        return f"{rebuilt_select}{remainder}"

    tail = remainder[group_by_match.end() :]
    tail_boundary = _ORDER_OR_LIMIT_PATTERN.search(tail)
    group_by_list = tail[: tail_boundary.start()] if tail_boundary else tail
    suffix = tail[tail_boundary.start() :] if tail_boundary else ""

    kept_group_by: list[str] = []
    for expression in _split_select_list(group_by_list):
        output_name = _expression_output_name(expression).lower()
        if output_name in valid_columns:
            kept_group_by.append(expression)

    if not kept_group_by:
        return f"{rebuilt_select}{remainder[: group_by_match.start()]}"

    return (
        f"{rebuilt_select}{remainder[: group_by_match.start()]}"
        f"GROUP BY {', '.join(kept_group_by)}{suffix}"
    )


def repair_clickhouse_select(
    sql_query: str,
    table_schema: TableSchema | None = None,
) -> str:
    """Fix frequent ClickHouse SQL issues before execution.

    Args:
        sql_query: Candidate SELECT query.
        table_schema: Optional schema for the target table.

    Returns:
        Repaired SELECT query string.
    """
    repaired = sql_query.strip().rstrip(";")
    repaired = _remove_invalid_any_without_group_by(repaired)
    if _GROUP_BY_PATTERN.search(repaired):
        repaired = _extend_group_by_for_bare_select_columns(repaired)
    if table_schema is not None:
        repaired = _filter_unknown_columns(repaired, table_schema)
    return repaired
