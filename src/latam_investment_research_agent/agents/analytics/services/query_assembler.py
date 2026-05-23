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

logger = logging.getLogger(__name__)

_SOURCE_REFERENCE_COLUMN = MANDATORY_AUDIT_COLUMNS[0]

_SYSTEM_PROMPT = f"""\
You are a ClickHouse SQL expert.  The user has a financial data question and you
must answer it by generating ClickHouse-compatible SELECT statements.

Rules:
- Return ONLY SELECT statements.  Never return INSERT, UPDATE, DELETE, DROP, or
  any other data-manipulation or schema-altering statement.
- Each query must include a LIMIT clause using the row limit provided.
- Use exact table and column names from the schemas provided.
- Every query MUST expose the document URL column ``{_SOURCE_REFERENCE_COLUMN}``:
  include it in the SELECT list for row-level queries, or use
  ``any({_SOURCE_REFERENCE_COLUMN}) AS {_SOURCE_REFERENCE_COLUMN}`` when using
  GROUP BY / aggregates.
- Prefer simple queries; join only when necessary.
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
        return stripped_query

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

    return f"{rewritten_select}{remainder}"


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
        f"Row limit per query: {export_row_limit}\n\n"
        f"Question: {question}"
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
            validated_queries.append(ensure_source_reference_in_select(query))
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
