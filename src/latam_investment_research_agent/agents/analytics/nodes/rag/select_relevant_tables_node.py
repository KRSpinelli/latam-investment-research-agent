"""RAG graph node: select relevant ClickHouse tables for the user's question.

Uses the LLM to identify which of the available tables are relevant to the
natural-language question.  Routes to build_rag_response_node when no tables
are selected.

See: data-model.md § RAGQueryState
     contracts/rag_query_graph.md § Node Sequence
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a data analyst assistant.  You will be shown a list of ClickHouse table
names and their columns, and a natural-language question.  Your task is to
identify which tables contain data relevant to answering the question.

The downstream pipeline has a large ClickHouse query budget. Include every table
that might contain useful figures — err on the side of inclusion (up to 10 tables).
Return only the table names that are relevant.  If no tables are relevant,
return an empty list.
"""


class _TableSelectionResponse(BaseModel):
    """Structured LLM response containing selected table names.

    Attributes:
        selected_table_names: Names of tables relevant to the question.
    """

    selected_table_names: list[str]


def _format_table_summaries(schemas: list[Any]) -> str:
    """Format table schemas as a compact text block for the selection prompt.

    Args:
        schemas: List of TableSchema objects to summarize.

    Returns:
        A newline-separated string with table names and column names.
    """
    lines: list[str] = []
    for schema in schemas:
        column_names = ", ".join(column.column_name for column in schema.columns)
        lines.append(f"- {schema.table_name}: {column_names}")
    return "\n".join(lines)


async def select_relevant_tables_node(
    state: RAGQueryState,
    llm: BaseChatModel,
) -> dict[str, Any]:
    """Select tables relevant to the user's question using the LLM.

    Passes all available table names and column lists to the LLM and asks it
    to identify which tables are likely to contain relevant data.  Sets
    ``error`` in state when no tables are selected.

    Args:
        state: The current RAG query graph state.
        llm: A ``BaseChatModel`` instance used for table selection.

    Returns:
        A dict with ``selected_table_names`` (list[str]) on success, or
        ``error`` set to "No relevant tables found" when the LLM selects none.
    """
    available_schemas = state.get("available_table_schemas", [])
    question = state["natural_language_question"]

    table_summaries = _format_table_summaries(available_schemas)
    user_message = (
        f"Available tables:\n{table_summaries}\n\n"
        f"Question: {question}\n\n"
        "Which tables are relevant to answer this question?"
    )

    structured_llm = llm.with_structured_output(_TableSelectionResponse)
    response: _TableSelectionResponse = await structured_llm.ainvoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    if not response.selected_table_names:
        logger.info("LLM selected no relevant tables for question: %r", question[:80])
        return {"selected_table_names": [], "error": "No relevant tables found"}

    logger.info("LLM selected %d relevant table(s).", len(response.selected_table_names))
    return {"selected_table_names": response.selected_table_names}
