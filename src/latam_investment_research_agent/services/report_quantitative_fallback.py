"""Guaranteed ClickHouse quantitative reads for analyst reports.

Reports must never ship with zero quantitative rows when any ClickHouse table
contains data. This module escalates through progressively broader strategies
until a minimum row budget is met.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from latam_investment_research_agent.agents.analytics.models.domain import TableSchema
from latam_investment_research_agent.agents.analytics.repositories.schema_repository import (
    get_all_table_schemas,
)
from latam_investment_research_agent.schemas.research import IngestionSummaryResponse

logger = logging.getLogger(__name__)

_TABLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_MINIMUM_REPORT_ROWS = 25
_ROW_LIMIT_PER_TABLE = 1_000
_MAX_TABLES_TO_PROBE = 20

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "from",
        "with",
        "what",
        "were",
        "that",
        "this",
        "into",
        "about",
        "have",
        "has",
        "how",
        "when",
        "where",
        "which",
        "their",
        "there",
        "been",
        "being",
        "will",
        "would",
        "could",
        "should",
        "than",
        "then",
        "also",
        "only",
        "some",
        "such",
        "over",
        "under",
        "more",
        "most",
        "much",
        "many",
        "year",
        "years",
    }
)


@dataclass
class QuantitativeDataBundle:
    """Rows and metadata after the guaranteed-quantitative pipeline."""

    rows: list[dict[str, Any]]
    sql_queries: list[str] = field(default_factory=list)
    data_source_note: str = ""


def _query_tokens(query: str) -> set[str]:
    """Extract lowercase keyword tokens from a research question.

    Args:
        query: Natural-language research question.

    Returns:
        Set of tokens length >= 3, excluding common stopwords.
    """
    tokens: set[str] = set()
    for word in re.findall(r"[a-z]{3,}", query.lower()):
        if word not in _STOPWORDS:
            tokens.add(word)
    return tokens


def _score_table_relevance(schema: TableSchema, tokens: set[str]) -> int:
    """Score how well a table schema matches query tokens.

    Args:
        schema: ClickHouse table schema.
        tokens: Keywords from the research question.

    Returns:
        Non-negative relevance score (higher is more relevant).
    """
    if not tokens:
        return 0
    score = 0
    table_name_lower = schema.table_name.lower()
    for token in tokens:
        if token in table_name_lower:
            score += 5
    for column in schema.columns:
        column_name_lower = column.column_name.lower()
        for token in tokens:
            if token in column_name_lower:
                score += 1
    return score


def _collect_ingested_table_names(
    ingestion_summaries: list[IngestionSummaryResponse],
) -> list[str]:
    """Return unique table names written during this research session.

    Args:
        ingestion_summaries: Per-URL ClickHouse ingestion outcomes.

    Returns:
        Ordered list of valid table names.
    """
    table_names: list[str] = []
    for summary in ingestion_summaries:
        for dataset in summary.datasets_succeeded:
            name = dataset.target_table_name.strip().lower()
            if name and _TABLE_NAME_PATTERN.match(name) and name not in table_names:
                table_names.append(name)
    return table_names


def _order_tables_for_query(
    table_names: list[str],
    schemas_by_name: dict[str, TableSchema],
    query: str,
) -> list[str]:
    """Sort table names with query-relevant tables first.

    Args:
        table_names: Candidate ClickHouse table names.
        schemas_by_name: Schema lookup by table name.
        query: Research question.

    Returns:
        Table names sorted by descending relevance.
    """
    tokens = _query_tokens(query)

    def sort_key(name: str) -> tuple[int, str]:
        schema = schemas_by_name.get(name)
        if schema is None:
            return (0, name)
        return (-_score_table_relevance(schema, tokens), name)

    return sorted(table_names, key=sort_key)


async def _fetch_rows_from_table(
    clickhouse_client: Any,
    table_name: str,
    *,
    row_limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Load a snapshot of rows from one table.

    Args:
        clickhouse_client: Async ClickHouse client.
        table_name: Validated table name.
        row_limit: Maximum rows to return.

    Returns:
        Tuple of row dicts and the SQL used, or empty list and None on failure.
    """
    if not _TABLE_NAME_PATTERN.match(table_name):
        return [], None

    queries_to_try = [
        (
            f"SELECT source_reference, * EXCEPT (source_reference) "
            f"FROM {table_name} "
            f"ORDER BY ingestion_timestamp DESC "
            f"LIMIT {row_limit}"
        ),
        f"SELECT * FROM {table_name} LIMIT {row_limit}",
    ]

    for sql_query in queries_to_try:
        try:
            query_result = await clickhouse_client.query(sql_query)
            column_names = query_result.column_names
            rows = [
                dict(zip(column_names, row, strict=True))
                for row in query_result.result_rows
            ]
            if rows:
                for row in rows:
                    row["_snapshot_table"] = table_name
                return rows, sql_query
        except Exception as error:
            logger.debug("Snapshot query failed for %s: %s", table_name, error)

    return [], None


async def _append_table_snapshots(
    clickhouse_client: Any,
    table_names: list[str],
    *,
    existing_rows: list[dict[str, Any]],
    sql_queries: list[str],
    row_limit_per_table: int,
    max_tables: int,
    minimum_rows: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Probe tables until the minimum row budget is met.

    Args:
        clickhouse_client: Async ClickHouse client.
        table_names: Tables to probe in order.
        existing_rows: Rows collected so far.
        sql_queries: SQL strings executed so far.
        row_limit_per_table: Row cap per table snapshot.
        max_tables: Maximum tables to query.
        minimum_rows: Stop when row count reaches this threshold.

    Returns:
        Updated rows and SQL query lists.
    """
    rows = list(existing_rows)
    queries = list(sql_queries)
    tables_probed = 0

    for table_name in table_names:
        if len(rows) >= minimum_rows:
            break
        if tables_probed >= max_tables:
            break

        snapshot_rows, sql_query = await _fetch_rows_from_table(
            clickhouse_client,
            table_name,
            row_limit=row_limit_per_table,
        )
        tables_probed += 1

        if not snapshot_rows or sql_query is None:
            continue

        rows.extend(snapshot_rows)
        queries.append(sql_query)
        logger.info(
            "Quantitative snapshot: %d row(s) from %s (total=%d)",
            len(snapshot_rows),
            table_name,
            len(rows),
        )

    return rows, queries


async def fetch_ingested_table_snapshots(
    ingestion_summaries: list[IngestionSummaryResponse],
    clickhouse_client: Any,
    *,
    row_limit_per_table: int = _ROW_LIMIT_PER_TABLE,
    max_tables: int = _MAX_TABLES_TO_PROBE,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load recent rows from tables written during this research session.

    Args:
        ingestion_summaries: Per-URL ClickHouse ingestion outcomes.
        clickhouse_client: Async ClickHouse client.
        row_limit_per_table: Maximum rows to read per table.
        max_tables: Maximum distinct tables to query.

    Returns:
        Tuple of merged row dicts and the SQL strings executed.
    """
    table_names = _collect_ingested_table_names(ingestion_summaries)[:max_tables]
    if not table_names:
        return [], []

    return await _append_table_snapshots(
        clickhouse_client,
        table_names,
        existing_rows=[],
        sql_queries=[],
        row_limit_per_table=row_limit_per_table,
        max_tables=max_tables,
        minimum_rows=1,
    )


async def ensure_quantitative_data(
    query: str,
    ingestion_summaries: list[IngestionSummaryResponse],
    clickhouse_client: Any,
    *,
    existing_rows: list[dict[str, Any]] | None = None,
    existing_sql_queries: list[str] | None = None,
    minimum_rows: int = _MINIMUM_REPORT_ROWS,
) -> QuantitativeDataBundle:
    """Guarantee a minimum number of quantitative rows for report generation.

    Escalation order:
    1. Keep rows already returned by the RAG graph (if sufficient).
    2. Snapshot tables ingested in this research session.
    3. Snapshot query-relevant tables from the full ClickHouse schema.
    4. Snapshot any remaining tables until rows exist or all are exhausted.

    Args:
        query: Research question (used for table relevance ranking).
        ingestion_summaries: ClickHouse ingestion outcomes from this session.
        clickhouse_client: Async ClickHouse client.
        existing_rows: Rows already collected (e.g. from RAG).
        existing_sql_queries: SQL already executed.
        minimum_rows: Target minimum row count.

    Returns:
        Bundle with rows, SQL audit trail, and a human-readable source note.
    """
    rows = list(existing_rows or [])
    sql_queries = list(existing_sql_queries or [])
    notes: list[str] = []

    if len(rows) >= minimum_rows:
        return QuantitativeDataBundle(
            rows=rows,
            sql_queries=sql_queries,
            data_source_note="Primary RAG query supplied sufficient quantitative rows.",
        )

    if rows:
        notes.append(
            f"RAG returned {len(rows)} row(s); broadening with table snapshots."
        )
    else:
        notes.append("RAG returned no rows; loading ClickHouse table snapshots.")

    ingested_names = _collect_ingested_table_names(ingestion_summaries)
    if ingested_names:
        rows, sql_queries = await _append_table_snapshots(
            clickhouse_client,
            ingested_names,
            existing_rows=rows,
            sql_queries=sql_queries,
            row_limit_per_table=_ROW_LIMIT_PER_TABLE,
            max_tables=_MAX_TABLES_TO_PROBE,
            minimum_rows=minimum_rows,
        )
        if len(rows) >= minimum_rows:
            notes.append(
                f"Session-ingested tables supplied {len(rows)} total row(s)."
            )
            return QuantitativeDataBundle(
                rows=rows,
                sql_queries=sql_queries,
                data_source_note=" ".join(notes),
            )

    schemas = await get_all_table_schemas(clickhouse_client)
    if not schemas:
        notes.append("ClickHouse has no tables; quantitative section will be empty.")
        return QuantitativeDataBundle(
            rows=rows,
            sql_queries=sql_queries,
            data_source_note=" ".join(notes),
        )

    schemas_by_name = {schema.table_name.lower(): schema for schema in schemas}
    all_table_names = [
        name
        for name in schemas_by_name
        if _TABLE_NAME_PATTERN.match(name)
    ]
    ranked_names = _order_tables_for_query(all_table_names, schemas_by_name, query)

    remaining_names = [name for name in ranked_names if name not in ingested_names]
    if remaining_names:
        rows, sql_queries = await _append_table_snapshots(
            clickhouse_client,
            remaining_names,
            existing_rows=rows,
            sql_queries=sql_queries,
            row_limit_per_table=_ROW_LIMIT_PER_TABLE,
            max_tables=_MAX_TABLES_TO_PROBE,
            minimum_rows=minimum_rows,
        )

    if rows:
        notes.append(
            f"Loaded {len(rows)} quantitative row(s) from ClickHouse snapshots "
            f"(query-ranked and/or session-ingested tables). "
            "Use these figures as supporting market context even when they do not "
            "name individual exporters."
        )
    else:
        notes.append(
            "All snapshot strategies returned zero rows; check ClickHouse connectivity "
            "and prior ingestion runs."
        )

    return QuantitativeDataBundle(
        rows=rows,
        sql_queries=sql_queries,
        data_source_note=" ".join(notes),
    )
