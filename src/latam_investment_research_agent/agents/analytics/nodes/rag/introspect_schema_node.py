"""RAG graph node: introspect ClickHouse schema.

Fetches all table schemas from ClickHouse and stores them in state.
Routes to build_rag_response_node when no tables are found.

See: data-model.md § RAGQueryState
     contracts/rag_query_graph.md § Node Sequence
"""

from __future__ import annotations

import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState
from latam_investment_research_agent.agents.analytics.repositories.schema_repository import (
    get_all_table_schemas,
)

logger = logging.getLogger(__name__)


async def introspect_schema_node(
    state: RAGQueryState,
    clickhouse_client: Any,
) -> dict[str, Any]:
    """Fetch all available table schemas from ClickHouse.

    Sets ``error`` in state when no tables exist so the conditional edge can
    route directly to ``build_rag_response_node`` without invoking the LLM.

    Args:
        state: The current RAG query graph state.
        clickhouse_client: An async clickhouse_connect client instance.

    Returns:
        A dict with ``available_table_schemas`` (list[TableSchema]) on success,
        or ``error`` set to "No tables found" when ClickHouse is empty.
    """
    schemas = await get_all_table_schemas(clickhouse_client)

    if not schemas:
        logger.warning("No tables found in ClickHouse; cannot answer query.")
        return {"available_table_schemas": [], "error": "No tables found"}

    logger.info("Introspected %d ClickHouse table(s).", len(schemas))
    return {"available_table_schemas": schemas}
