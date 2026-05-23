"""RAG graph node: assemble SELECT-only SQL queries for the user's question.

Filters available schemas to only the selected tables, then calls the query
assembler service to generate ClickHouse-compatible SELECT statements.

See: contracts/rag_query_graph.md § Node Sequence
     plan.md § RAG Query: SELECT-Only Guard
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState
from latam_investment_research_agent.agents.analytics.services.exploratory_queries import (
    build_exploratory_queries,
)
from latam_investment_research_agent.agents.analytics.services.query_assembler import (
    _MAX_TOTAL_QUERIES,
    assemble_queries,
)
from latam_investment_research_agent.agents.analytics.services.sql_query_repair import (
    extract_table_name,
    repair_clickhouse_select,
)

logger = logging.getLogger(__name__)


async def assemble_queries_node(
    state: RAGQueryState,
    llm: BaseChatModel,
) -> dict[str, Any]:
    """Generate SELECT-only SQL queries for the selected tables and question.

    Filters the available table schemas to only those whose names appear in
    ``state["selected_table_names"]``, then delegates to the query assembler
    service which enforces the SELECT-only guard.

    Each query includes a LIMIT clause equal to ``state["export_row_limit"]``
    so the database never returns more rows than the export pipeline can handle.

    Args:
        state: The current RAG query graph state.
        llm: A ``BaseChatModel`` instance used to generate SQL.

    Returns:
        A dict with ``assembled_sql_queries`` (list[str]).  May be empty if
        the LLM returns no valid SELECT queries.
    """
    selected_names = set(state.get("selected_table_names", []))
    available_schemas = state.get("available_table_schemas", [])
    question = state["natural_language_question"]
    export_row_limit = state.get("export_row_limit", 10_000)

    selected_schemas = [
        schema for schema in available_schemas if schema.table_name in selected_names
    ]

    logger.info(
        "Assembling queries for question %r against %d table(s).",
        question[:60],
        len(selected_schemas),
    )

    language_model_queries = await assemble_queries(
        question=question,
        selected_schemas=selected_schemas,
        llm=llm,
        export_row_limit=export_row_limit,
    )
    template_queries = build_exploratory_queries(
        selected_schemas,
        row_limit=min(export_row_limit, 10_000),
        max_queries_per_table=4,
    )

    schemas_by_table = {schema.table_name.lower(): schema for schema in selected_schemas}
    merged_queries: list[str] = []
    seen_queries: set[str] = set()
    for sql_query in [*language_model_queries, *template_queries]:
        table_name = extract_table_name(sql_query)
        table_schema = schemas_by_table.get(table_name) if table_name else None
        normalized = repair_clickhouse_select(
            sql_query.strip().rstrip(";"),
            table_schema,
        )
        if normalized and normalized not in seen_queries:
            seen_queries.add(normalized)
            merged_queries.append(normalized)
        if len(merged_queries) >= _MAX_TOTAL_QUERIES:
            break

    logger.info(
        "Assembled %d total queries (%d from LLM, %d template).",
        len(merged_queries),
        len(language_model_queries),
        len(template_queries),
    )

    return {"assembled_sql_queries": merged_queries}
