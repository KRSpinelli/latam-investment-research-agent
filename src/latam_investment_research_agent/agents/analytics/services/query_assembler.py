"""RAG service: assemble SELECT-only SQL queries from a natural-language question.

Calls the LLM with the selected table schemas and the user's question.
All queries returned must start with SELECT; non-SELECT responses are
silently discarded with a logged warning.

See: plan.md § RAG Query: SELECT-Only Guard
     contracts/rag_query_graph.md § Node Sequence
"""

from __future__ import annotations

import logging
import re

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from latam_investment_research_agent.agents.analytics.constants import MANDATORY_AUDIT_COLUMNS
from latam_investment_research_agent.agents.analytics.models.domain import TableSchema
from latam_investment_research_agent.agents.analytics.services.sql_query_repair import (
    repair_clickhouse_select,
)

logger = logging.getLogger(__name__)

_SOURCE_REFERENCE_COLUMN = MANDATORY_AUDIT_COLUMNS[0]

_MINIMUM_LLM_QUERIES = 12
_MAX_TOTAL_QUERIES = 30

_SYSTEM_PROMPT = f"""\
You are a ClickHouse SQL expert.  The user has a financial data question and you
must answer it by generating ClickHouse-compatible SELECT statements.

Query budget: the caller has generous ClickHouse capacity — generate many queries.
Produce at least {_MINIMUM_LLM_QUERIES} distinct SELECT statements when schemas allow.
Explore every relevant table from multiple angles (raw rows, time trends, totals,
breakdowns by categorical columns). Prefer breadth and variety over a single minimal query.

Rules:
- Return ONLY SELECT statements.  Never return INSERT, UPDATE, DELETE, DROP, or
  any other data-manipulation or schema-altering statement.
- Each query must include a LIMIT clause using the row limit provided.
- Use exact table and column names from the schemas provided.
- Every query MUST expose the document URL column ``{_SOURCE_REFERENCE_COLUMN}``:
  include it as a plain column for row-level queries. For GROUP BY queries, use
  ``any({_SOURCE_REFERENCE_COLUMN}) AS {_SOURCE_REFERENCE_COLUMN}`` and list every
  non-aggregated SELECT column in GROUP BY.
- Prefer simple queries; join only when necessary.
- When using aggregate functions (SUM, COUNT, any, etc.), every non-aggregated
  column in the SELECT list MUST appear in GROUP BY (ClickHouse strict mode).
- Use ONLY column names that appear in the provided schemas. Never invent columns
  (for example ``producer``, ``location``, ``prize_amount``, ``country``).
- Prefer simple ``SELECT ... FROM table ORDER BY ... LIMIT`` without WHERE unless
  the filter column is explicitly listed in the schema.
- Do not explain the queries — return only the SQL text.
"""


class _QueryListResponse(BaseModel):
    """Structured LLM response containing a list of SQL query strings.

    Attributes:
        sql_queries: One or more SELECT statements answering the question.
    """

    sql_queries: list[str]


def _format_schemas_for_prompt(schemas: list[TableSchema]) -> str:
    """Format table schemas into a compact text block for the LLM prompt.

    Args:
        schemas: The list of table schemas to include in the prompt.

    Returns:
        A newline-separated string of table name and column definitions.
    """
    lines: list[str] = []
    for schema in schemas:
        column_descriptions = ", ".join(
            f"{column.column_name} {column.column_type}" for column in schema.columns
        )
        lines.append(f"TABLE {schema.table_name} ({column_descriptions})")
    return "\n".join(lines)


def _schema_for_query(
    sql_query: str,
    selected_schemas: list[TableSchema],
) -> TableSchema | None:
    """Resolve the table schema used by a SELECT query.

    Args:
        sql_query: SQL query string.
        selected_schemas: Schemas available to the assembler.

    Returns:
        Matching TableSchema or None.
    """
    from latam_investment_research_agent.agents.analytics.services.sql_query_repair import (
        extract_table_name,
    )

    table_name = extract_table_name(sql_query)
    if table_name is None:
        return None
    for schema in selected_schemas:
        if schema.table_name.lower() == table_name:
            return schema
    return None


def _is_select_query(query: str) -> bool:
    """Return True if the query string begins with SELECT (case-insensitive).

    Args:
        query: The SQL string to check.

    Returns:
        True when the stripped, uppercased query starts with ``SELECT``.
    """
    return query.strip().upper().startswith("SELECT")


def ensure_source_reference_in_select(sql_query: str) -> str:
    """Ensure a SELECT query returns the ``source_reference`` audit column.

    When the LLM omits ``source_reference``, this function rewrites the SELECT
    list so exports can always include the ingested document URL.

    Args:
        sql_query: A validated SELECT query string.

    Returns:
        The same query, or a rewritten query that includes ``source_reference``.
    """
    stripped_query = sql_query.strip().rstrip(";")
    if _SOURCE_REFERENCE_COLUMN in stripped_query.lower():
        return repair_clickhouse_select(stripped_query)

    from_match = re.search(r"\s+from\s+", stripped_query, flags=re.IGNORECASE)
    if from_match is None:
        return stripped_query

    select_clause = stripped_query[: from_match.start()]
    remainder = stripped_query[from_match.start() :]

    if re.fullmatch(r"(?is)\s*select\s+\*\s*", select_clause):
        return stripped_query

    select_list = re.sub(r"(?is)^\s*select\s+", "", select_clause).strip()
    if not select_list:
        return stripped_query

    if re.search(r"(?i)\bgroup\s+by\b", remainder):
        rewritten_select = (
            f"SELECT {select_list}, "
            f"any({_SOURCE_REFERENCE_COLUMN}) AS {_SOURCE_REFERENCE_COLUMN}"
        )
    else:
        rewritten_select = f"SELECT {_SOURCE_REFERENCE_COLUMN}, {select_list}"
    return repair_clickhouse_select(f"{rewritten_select}{remainder}")


async def assemble_queries(
    question: str,
    selected_schemas: list[TableSchema],
    llm: BaseChatModel,
    export_row_limit: int = 10_000,
) -> list[str]:
    """Assemble SELECT-only SQL queries that answer the natural-language question.

    Invokes the LLM with the selected table schemas and the user's question,
    requesting a structured list of SQL strings.  Any query that does not start
    with SELECT is discarded and a warning is logged.

    Args:
        question: The natural-language question to answer with SQL.
        selected_schemas: Table schemas the LLM may query.
        llm: A ``BaseChatModel`` instance used to generate the queries.
        export_row_limit: Maximum rows each query should return; injected into
            the prompt so the LLM includes an appropriate LIMIT clause.

    Returns:
        A list of validated SELECT query strings.  May be empty if the LLM
        returns no valid queries.
    """
    if not selected_schemas:
        logger.warning("assemble_queries called with no selected schemas — returning empty list.")
        return []

    schema_text = _format_schemas_for_prompt(selected_schemas)
    user_message = (
        f"Available tables:\n{schema_text}\n\n"
        f"Row limit per query: {export_row_limit}\n"
        f"Minimum queries to return: {_MINIMUM_LLM_QUERIES}\n\n"
        f"Question: {question}\n\n"
        "Generate diverse queries — totals, rankings, time series, and segment breakdowns. "
        "Use the full query budget; more exploration is better."
    )

    structured_llm = llm.with_structured_output(_QueryListResponse)
    response: _QueryListResponse = await structured_llm.ainvoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    validated_queries: list[str] = []
    for query in response.sql_queries:
        if _is_select_query(query):
            rewritten = ensure_source_reference_in_select(query)
            validated_queries.append(
                repair_clickhouse_select(rewritten, _schema_for_query(rewritten, selected_schemas))
            )
        else:
            logger.warning(
                "LLM returned a non-SELECT query — discarding: %r",
                query[:120],
            )

    logger.info(
        "Query assembly complete: %d valid SELECT queries (discarded %d non-SELECT)",
        len(validated_queries),
        len(response.sql_queries) - len(validated_queries),
    )
    return validated_queries
