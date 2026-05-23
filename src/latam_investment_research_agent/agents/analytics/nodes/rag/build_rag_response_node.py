"""RAG graph node: build the final RAG query output.

The terminal node in the RAG query graph.  Assembles RAGQueryOutput from
accumulated state and handles both the happy path (CSV exported) and the
empty-result / error path (no file, explanatory rationale).

See: data-model.md § RAGQueryOutput
     contracts/rag_query_graph.md § Node Sequence
"""

from __future__ import annotations

import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.rag_state import (
    RAGQueryOutput,
    RAGQueryState,
)

logger = logging.getLogger(__name__)

_NO_DATA_RATIONALE = "No relevant data found for this question."
_TRUNCATION_SUFFIX = (
    "  Note: results were truncated to the configured export row limit."
)


async def build_rag_response_node(state: RAGQueryState) -> dict[str, Any]:
    """Compile the final RAGQueryOutput from the completed graph state.

    Handles three cases:
    1. Early exit via error (no tables found, no relevant tables): returns
       ``RAGQueryOutput`` with ``export_file_path=None`` and explanatory
       rationale from ``state["error"]``.
    2. Queries ran but returned no rows: rationale is set to the standard
       "No relevant data found" message.
    3. Successful export: rationale is composed from the assembled queries;
       a truncation note is appended when ``was_truncated`` is True.

    Args:
        state: The final RAG query graph state.

    Returns:
        A dict with ``rag_query_output`` containing a ``RAGQueryOutput`` dict.
    """
    export_file_path: str | None = state.get("export_file_path")
    assembled_queries: list[str] = state.get("assembled_sql_queries", [])
    query_result_records: list[Any] = state.get("query_result_records", [])
    was_truncated: bool = state.get("was_truncated", False)
    error: str | None = state.get("error")
    question: str = state["natural_language_question"]

    if error and export_file_path is None:
        rationale = error
    elif export_file_path is None:
        rationale = _NO_DATA_RATIONALE
    else:
        query_summary = "; ".join(q[:60] + ("..." if len(q) > 60 else "") for q in assembled_queries)
        rationale = (
            f"Data retrieved from ClickHouse to answer: '{question}'.  "
            f"Queries used: {query_summary}."
        )
        if was_truncated:
            rationale += _TRUNCATION_SUFFIX

    row_count = len(query_result_records)

    output: RAGQueryOutput = {
        "export_file_path": export_file_path,
        "rationale": rationale,
        "sql_queries_used": assembled_queries,
        "row_count": row_count,
        "was_truncated": was_truncated,
    }

    logger.info(
        "RAG query complete — file: %s, rows: %d, truncated: %s",
        export_file_path or "none",
        row_count,
        was_truncated,
    )

    return {"rag_query_output": output}
