"""Compiled LangGraph ingestion graph.

Builds and compiles the document ingestion workflow as a module-level
singleton.  Import ``ingestion_graph`` and call ``await ingestion_graph.ainvoke(input)``
from the parent orchestrator.

Graph flow::

    START
      → fetch_document
      → extract_numerical_data  ── (0 datasets) ──────────────────────────┐
      → route_dataset          ◄──────────────────┐                       │
      → write_to_clickhouse    ──────────────────► │ (loops while remain) │
      → build_ingestion_summary ◄──────────────────────────────────────── ┘
    END

A conditional edge after ``fetch_document`` routes directly to
``build_ingestion_summary`` on fatal fetch failure (``error`` set in state).
A conditional edge after ``extract_numerical_data`` routes directly to
``build_ingestion_summary`` when no datasets were extracted (empty list).
A conditional edge after ``write_to_clickhouse`` routes back to
``route_dataset`` while ``current_dataset_index < len(extracted_datasets)``.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig
from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.nodes.ingestion.build_ingestion_summary_node import (
    build_ingestion_summary_node,
)
from latam_investment_research_agent.agents.analytics.nodes.ingestion.extract_numerical_data_node import (
    extract_numerical_data_node,
)
from latam_investment_research_agent.agents.analytics.nodes.ingestion.fetch_document_node import (
    fetch_document_node,
)
from latam_investment_research_agent.agents.analytics.nodes.ingestion.route_dataset_node import (
    route_dataset_node,
)
from latam_investment_research_agent.agents.analytics.nodes.ingestion.write_to_clickhouse_node import (
    write_to_clickhouse_node,
)
from latam_investment_research_agent.agents.analytics.providers.llm_provider import (
    create_llm_provider,
)

logger = logging.getLogger(__name__)


def _should_continue_after_fetch(
    state: IngestionState,
) -> Literal["extract_numerical_data", "build_ingestion_summary"]:
    """Route after fetch_document: skip to summary on fatal error.

    Args:
        state: Current graph state.

    Returns:
        Next node name.
    """
    if state.get("error"):
        return "build_ingestion_summary"
    return "extract_numerical_data"


def _should_continue_after_extraction(
    state: IngestionState,
) -> Literal["route_dataset", "build_ingestion_summary"]:
    """Route after extract_numerical_data: skip to summary when nothing was found.

    Args:
        state: Current graph state.

    Returns:
        ``"route_dataset"`` when at least one dataset was extracted;
        ``"build_ingestion_summary"`` when the list is empty.
    """
    if not state.get("extracted_datasets"):
        logger.info("No datasets extracted — routing directly to summary.")
        return "build_ingestion_summary"
    return "route_dataset"


def _should_continue_dataset_loop(
    state: IngestionState,
) -> Literal["route_dataset", "build_ingestion_summary"]:
    """Route after write_to_clickhouse: loop or finish.

    Args:
        state: Current graph state.

    Returns:
        ``"route_dataset"`` while more datasets remain;
        ``"build_ingestion_summary"`` when all are processed.
    """
    current_index: int = state.get("current_dataset_index", 0)
    extracted_datasets = state.get("extracted_datasets", [])
    if current_index < len(extracted_datasets):
        return "route_dataset"
    return "build_ingestion_summary"


def build_ingestion_graph(
    config: AnalyticsConfig | None = None,
    llm: BaseChatModel | None = None,
    clickhouse_client: Any = None,
) -> Any:
    """Build and compile the ingestion LangGraph.

    Dependencies (LLM, ClickHouse client) can be injected for testing.  In
    production the graph reads from ``AnalyticsConfig`` and creates the client
    at build time.

    Args:
        config: Analytics configuration.  Created from environment if ``None``.
        llm: A ``BaseChatModel`` to inject.  Created via factory if ``None``.
        clickhouse_client: A clickhouse_connect async client.  Created from
            ``config`` if ``None``.

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready for ``ainvoke``.
    """
    if llm is None:
        if config is None:
            config = AnalyticsConfig()
        llm = create_llm_provider(config)

    graph_builder: StateGraph = StateGraph(IngestionState)

    graph_builder.add_node("fetch_document", fetch_document_node)
    graph_builder.add_node(
        "extract_numerical_data",
        functools.partial(extract_numerical_data_node, llm=llm),
    )
    graph_builder.add_node(
        "route_dataset",
        functools.partial(route_dataset_node, llm=llm, clickhouse_client=clickhouse_client),
    )
    graph_builder.add_node(
        "write_to_clickhouse",
        functools.partial(write_to_clickhouse_node, clickhouse_client=clickhouse_client),
    )
    graph_builder.add_node("build_ingestion_summary", build_ingestion_summary_node)

    graph_builder.add_edge(START, "fetch_document")
    graph_builder.add_conditional_edges(
        "fetch_document",
        _should_continue_after_fetch,
        {
            "extract_numerical_data": "extract_numerical_data",
            "build_ingestion_summary": "build_ingestion_summary",
        },
    )
    graph_builder.add_conditional_edges(
        "extract_numerical_data",
        _should_continue_after_extraction,
        {
            "route_dataset": "route_dataset",
            "build_ingestion_summary": "build_ingestion_summary",
        },
    )
    graph_builder.add_edge("route_dataset", "write_to_clickhouse")
    graph_builder.add_conditional_edges(
        "write_to_clickhouse",
        _should_continue_dataset_loop,
        {
            "route_dataset": "route_dataset",
            "build_ingestion_summary": "build_ingestion_summary",
        },
    )
    graph_builder.add_edge("build_ingestion_summary", END)

    return graph_builder.compile()


# Module-level singleton — compiled once at import time.
# Falls back to None when required environment variables are absent (e.g. in
# test environments where dependencies are injected via build_ingestion_graph).
try:
    ingestion_graph = build_ingestion_graph()
except Exception:  # noqa: BLE001
    logger.debug(
        "ingestion_graph singleton skipped — environment variables not configured. "
        "Use build_ingestion_graph() with explicit dependencies instead."
    )
    ingestion_graph = None  # type: ignore[assignment]
