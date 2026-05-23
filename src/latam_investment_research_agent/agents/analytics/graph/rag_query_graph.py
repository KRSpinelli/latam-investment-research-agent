"""Compiled LangGraph RAG query graph.

Builds and compiles the RAG query workflow as a module-level singleton.
Import ``rag_query_graph`` and call ``await rag_query_graph.ainvoke(input)``
from the parent orchestrator.

Graph flow::

    START
      → introspect_schema        ─── (error: no tables) ──────────────────┐
      → select_relevant_tables   ─── (error: no relevant tables) ──────────┤
      → assemble_queries                                                    │
      → execute_queries                                                     │
      → export_results                                                      │
      → build_rag_response   ◄──────────────────────────────────────────── ┘
    END

The graph is read-only with respect to ClickHouse — no node issues DML.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig
from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState
from latam_investment_research_agent.agents.analytics.nodes.rag.assemble_queries_node import (
    assemble_queries_node,
)
from latam_investment_research_agent.agents.analytics.nodes.rag.build_rag_response_node import (
    build_rag_response_node,
)
from latam_investment_research_agent.agents.analytics.nodes.rag.execute_queries_node import (
    execute_queries_node,
)
from latam_investment_research_agent.agents.analytics.nodes.rag.export_results_node import (
    export_results_node,
)
from latam_investment_research_agent.agents.analytics.nodes.rag.introspect_schema_node import (
    introspect_schema_node,
)
from latam_investment_research_agent.agents.analytics.nodes.rag.select_relevant_tables_node import (
    select_relevant_tables_node,
)
from latam_investment_research_agent.agents.analytics.providers.llm_provider import (
    create_llm_provider,
)

logger = logging.getLogger(__name__)


def _should_continue_after_introspect(
    state: RAGQueryState,
) -> Literal["select_relevant_tables", "build_rag_response"]:
    """Route after introspect_schema: skip to response when no tables found.

    Args:
        state: Current graph state.

    Returns:
        Next node name.
    """
    if state.get("error"):
        return "build_rag_response"
    return "select_relevant_tables"


def _should_continue_after_select(
    state: RAGQueryState,
) -> Literal["assemble_queries", "build_rag_response"]:
    """Route after select_relevant_tables: skip to response when no tables selected.

    Args:
        state: Current graph state.

    Returns:
        Next node name.
    """
    if state.get("error") or not state.get("selected_table_names"):
        return "build_rag_response"
    return "assemble_queries"


def build_rag_query_graph(
    config: AnalyticsConfig | None = None,
    llm: BaseChatModel | None = None,
    clickhouse_client: Any = None,
) -> Any:
    """Build and compile the RAG query LangGraph.

    Dependencies (LLM, ClickHouse client) can be injected for testing.  In
    production the graph reads from ``AnalyticsConfig`` and creates the LLM
    at build time.

    Args:
        config: Analytics configuration.  Created from environment if ``None``.
        llm: A ``BaseChatModel`` to inject.  Created via factory if ``None``.
        clickhouse_client: An async clickhouse_connect client.  Created from
            ``config`` if ``None``.

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready for ``ainvoke``.
    """
    if llm is None:
        if config is None:
            config = AnalyticsConfig()
        llm = create_llm_provider(config)

    graph_builder: StateGraph = StateGraph(RAGQueryState)

    graph_builder.add_node(
        "introspect_schema",
        functools.partial(introspect_schema_node, clickhouse_client=clickhouse_client),
    )
    graph_builder.add_node(
        "select_relevant_tables",
        functools.partial(select_relevant_tables_node, llm=llm),
    )
    graph_builder.add_node(
        "assemble_queries",
        functools.partial(assemble_queries_node, llm=llm),
    )
    graph_builder.add_node(
        "execute_queries",
        functools.partial(execute_queries_node, clickhouse_client=clickhouse_client),
    )
    graph_builder.add_node("export_results", export_results_node)
    graph_builder.add_node("build_rag_response", build_rag_response_node)

    graph_builder.add_edge(START, "introspect_schema")
    graph_builder.add_conditional_edges(
        "introspect_schema",
        _should_continue_after_introspect,
        {
            "select_relevant_tables": "select_relevant_tables",
            "build_rag_response": "build_rag_response",
        },
    )
    graph_builder.add_conditional_edges(
        "select_relevant_tables",
        _should_continue_after_select,
        {
            "assemble_queries": "assemble_queries",
            "build_rag_response": "build_rag_response",
        },
    )
    graph_builder.add_edge("assemble_queries", "execute_queries")
    graph_builder.add_edge("execute_queries", "export_results")
    graph_builder.add_edge("export_results", "build_rag_response")
    graph_builder.add_edge("build_rag_response", END)

    return graph_builder.compile()


# Module-level singleton — compiled once at import time.
# Falls back to None when required environment variables are absent (e.g. in
# test environments where dependencies are injected via build_rag_query_graph).
try:
    rag_query_graph = build_rag_query_graph()
except Exception:  # noqa: BLE001
    logger.debug(
        "rag_query_graph singleton skipped — environment variables not configured. "
        "Use build_rag_query_graph() with explicit dependencies instead."
    )
    rag_query_graph = None  # type: ignore[assignment]
