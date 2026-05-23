"""Normalize extracted rows and coerce values for ClickHouse inserts.

Financial PDF extraction often yields wide tables (years as column headers),
percentages, locale-formatted numbers, and label rows.  These helpers align row
keys with table schemas and coerce cell values before insert.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from latam_investment_research_agent.agents.analytics.constants import MANDATORY_AUDIT_COLUMNS
from latam_investment_research_agent.agents.analytics.models.domain import ColumnDefinition

_EMPTY_VALUE_MARKERS = frozenset({"", "-", "—", "n/a", "na", "none", "null"})


def normalize_column_key(column_key: str) -> str:
    """Convert an extracted column key into a safe ClickHouse identifier.

    Args:
        column_key: Raw column name from an extracted row dict.

    Returns:
        Snake_case identifier, prefixed when the name starts with a digit.
    """
    safe_name = (
        str(column_key)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("/", "_")
    )
    allowed_characters = set("abcdefghijklmnopqrstuvwxyz0123456789_")
    safe_name = "".join(character for character in safe_name if character in allowed_characters)
    while "__" in safe_name:
        safe_name = safe_name.replace("__", "_")
    safe_name = safe_name.strip("_")
    if not safe_name:
        return "unknown_column"
    if safe_name[0].isdigit():
        safe_name = f"col_{safe_name}"
    return safe_name[:64]


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize all column keys in extracted rows.

    Args:
        rows: Row dicts with arbitrary string keys.

    Returns:
        Rows whose keys are safe ClickHouse identifiers.
    """
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_row = {
            normalize_column_key(column_key): value
            for column_key, value in row.items()
            if column_key not in MANDATORY_AUDIT_COLUMNS
        }
        normalized_rows.append(normalized_row)
    return normalized_rows


def merge_schema_with_row_keys(
    proposed_schema: list[ColumnDefinition],
    rows: list[dict[str, Any]],
) -> list[ColumnDefinition]:
    """Merge LLM-proposed columns with every key present in extracted rows.

    Row keys missing from ``proposed_schema`` are added as ``String`` columns so
    wide tables (for example year columns ``col_2023``, ``col_2024``) match the
    physical table layout.

    Args:
        proposed_schema: Column definitions from the routing decision.
        rows: Normalized row dicts for one dataset.

    Returns:
        Combined column definitions for ``CREATE TABLE``.
    """
    columns_by_name: dict[str, ColumnDefinition] = {
        column.column_name: column for column in proposed_schema
    }
    for row in rows:
        for column_key in row:
            normalized_key = normalize_column_key(column_key)
            if normalized_key in MANDATORY_AUDIT_COLUMNS:
                continue
            if normalized_key not in columns_by_name:
                columns_by_name[normalized_key] = ColumnDefinition(
                    column_name=normalized_key,
                    clickhouse_type="String",
                    description="Auto-added to match extracted row keys.",
                )
    return list(columns_by_name.values())


def _quote_column_identifier(column_name: str) -> str:
    """Quote a column name for ClickHouse SQL when required.

    Args:
        column_name: Column identifier.

    Returns:
        Bare name or backtick-quoted name.
    """
    if column_name.isidentifier():
        return column_name
    escaped_name = column_name.replace("`", "``")
    return f"`{escaped_name}`"


def _strip_numeric_text(value: str) -> str:
    """Remove common formatting characters from a numeric string.

    Args:
        value: Raw cell text.

    Returns:
        Cleaned string suitable for parsing.
    """
    cleaned = value.strip()
    cleaned = cleaned.replace("%", "").replace("R$", "").replace("$", "").replace("€", "")
    cleaned = cleaned.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    return cleaned


def _parse_decimal_string(value: str) -> str:
    """Parse locale-formatted decimals into a ClickHouse-compatible string.

    Args:
        value: Raw cell text.

    Returns:
        Decimal string using a period as the decimal separator.
    """
    cleaned = _strip_numeric_text(value)
    if cleaned.lower() in _EMPTY_VALUE_MARKERS:
        return "0"

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return str(Decimal(cleaned))
    except InvalidOperation:
        numeric_match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if numeric_match:
            return numeric_match.group(0)
        return "0"


def coerce_cell_value(value: Any, clickhouse_type: str) -> Any:
    """Coerce one cell value to a type compatible with ClickHouse insert.

    Args:
        value: Raw extracted value.
        clickhouse_type: ClickHouse type string from ``DESCRIBE TABLE``.

    Returns:
        A value ``clickhouse-connect`` can serialize for the given column type.
    """
    if value is None:
        return ""

    type_upper = clickhouse_type.upper()
    text_value = str(value).strip()
    if text_value.lower() in _EMPTY_VALUE_MARKERS:
        if "INT" in type_upper or "UINT" in type_upper:
            return 0
        if "DECIMAL" in type_upper or "FLOAT" in type_upper or "DOUBLE" in type_upper:
            return "0"
        return ""

    if "STRING" in type_upper or "FIXEDSTRING" in type_upper:
        return text_value

    if "DATE" in type_upper:
        if text_value.replace(".", "").replace("-", "").replace(":", "").isdigit():
            digits_only = re.sub(r"[^0-9]", "", text_value)
            if len(digits_only) >= 8:
                return (
                    f"{digits_only[0:4]}-{digits_only[4:6]}-{digits_only[6:8]} "
                    f"00:00:00.000"
                )[:23]
        return text_value

    if "INT" in type_upper or "UINT" in type_upper:
        cleaned = _strip_numeric_text(text_value)
        try:
            if "." in cleaned:
                return int(float(cleaned))
            return int(cleaned.replace(",", ""))
        except ValueError:
            numeric_match = re.search(r"-?\d+", cleaned)
            return int(numeric_match.group(0)) if numeric_match else 0

    if "DECIMAL" in type_upper or "FLOAT" in type_upper or "DOUBLE" in type_upper:
        return _parse_decimal_string(text_value)

    return text_value
