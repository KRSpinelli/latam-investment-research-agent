"""Ingestion graph node: route the current dataset to a ClickHouse table.

Uses the LLM-based table router to determine whether the current dataset
should be appended to an existing table or written to a new one.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.models.domain import RoutingDecision
from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.repositories.schema_repository import (
    get_all_table_schemas,
)
from latam_investment_research_agent.agents.analytics.services.table_router import route_dataset

logger = logging.getLogger(__name__)


async def route_dataset_node(
    state: IngestionState,
    llm: BaseChatModel,
    clickhouse_client: Any,
) -> dict[str, Any]:
    """Determine the ClickHouse destination for the current dataset.

    Retrieves all existing table schemas from ClickHouse, then invokes the
    LLM-based router for the dataset at ``current_dataset_index``.  Stores
    the resulting ``RoutingDecision`` in state for the write node.

    Args:
        state: The current ingestion graph state.
        llm: A ``BaseChatModel`` instance injected by the graph factory.
        clickhouse_client: An async clickhouse_connect client instance.

    Returns:
        A dict containing ``routing_decision`` (RoutingDecision).
    """
    current_index: int = state.get("current_dataset_index", 0)
    extracted_datasets = state.get("extracted_datasets", [])
    current_dataset = extracted_datasets[current_index]

    logger.info(
        "Routing dataset %d/%d: '%s'",
        current_index + 1,
        len(extracted_datasets),
        current_dataset.dataset_name,
    )

    existing_schemas = await get_all_table_schemas(clickhouse_client)
    routing_decision: RoutingDecision = await route_dataset(
        current_dataset, existing_schemas, llm
    )

    return {"routing_decision": routing_decision}
