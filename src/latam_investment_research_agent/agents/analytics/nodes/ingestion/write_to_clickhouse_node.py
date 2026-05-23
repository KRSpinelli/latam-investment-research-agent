"""Ingestion graph node: write the current dataset to ClickHouse.

Applies the routing decision to either create a new table or append to an
existing one, then inserts rows with deduplication.  Failures are captured
as ``DatasetIngestionFailure`` objects and never re-raised, so that the graph
can continue processing remaining datasets.
"""

from __future__ import annotations

import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.domain import (
    DatasetIngestionFailure,
    DatasetIngestionResult,
    RoutingDecision,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.repositories.clickhouse_repository import (
    alter_table_add_columns,
    create_table,
    insert_rows_deduplicated,
)

logger = logging.getLogger(__name__)


def _determine_table_name(routing_decision: RoutingDecision, dataset_name: str) -> str:
    """Determine the final ClickHouse table name from a routing decision.

    When the routing action is ``"create"``, generates a snake_case table name
    from the dataset name.  Otherwise returns the existing table name from the
    routing decision.

    Args:
        routing_decision: The routing decision for this dataset.
        dataset_name: Human-readable name of the dataset, used to generate a
            new table name when ``routing_action == "create"``.

    Returns:
        The ClickHouse table name to use.
    """
    if routing_decision.routing_action == "create":
        safe_name = (
            dataset_name.lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        allowed_characters = set("abcdefghijklmnopqrstuvwxyz0123456789_")
        return "".join(character for character in safe_name if character in allowed_characters)[:64]
    return routing_decision.target_table_name


async def write_to_clickhouse_node(
    state: IngestionState,
    clickhouse_client: Any,
) -> dict[str, Any]:
    """Write the current dataset to ClickHouse using the routing decision.

    On success: appends a ``DatasetIngestionResult`` to ``ingestion_results``.
    On failure: appends a ``DatasetIngestionFailure`` to ``ingestion_failures``.
    Always increments ``current_dataset_index`` so the loop advances.

    Args:
        state: The current ingestion graph state.
        clickhouse_client: An async clickhouse_connect client instance.

    Returns:
        A dict updating ``ingestion_results``, ``ingestion_failures``,
        and ``current_dataset_index``.
    """
    current_index: int = state.get("current_dataset_index", 0)
    extracted_datasets = state.get("extracted_datasets", [])
    current_dataset = extracted_datasets[current_index]
    routing_decision: RoutingDecision = state["routing_decision"]

    existing_results: list[DatasetIngestionResult] = list(state.get("ingestion_results", []))
    existing_failures: list[DatasetIngestionFailure] = list(state.get("ingestion_failures", []))

    try:
        table_name = _determine_table_name(routing_decision, current_dataset.dataset_name)

        if routing_decision.routing_action == "create" and routing_decision.proposed_schema:
            await create_table(clickhouse_client, table_name, routing_decision.proposed_schema)
            logger.info("Created new table '%s'", table_name)
        elif routing_decision.routing_action == "append" and routing_decision.proposed_schema:
            await alter_table_add_columns(
                clickhouse_client, table_name, routing_decision.proposed_schema
            )

        rows_written = await insert_rows_deduplicated(
            clickhouse_client,
            table_name,
            current_dataset.rows,
            state["source_reference"],
        )

        existing_results.append(
            DatasetIngestionResult(
                dataset_name=current_dataset.dataset_name,
                target_table_name=table_name,
                routing_action=routing_decision.routing_action,
                rows_written=rows_written,
            )
        )
        logger.info(
            "Wrote %d rows for dataset '%s' to table '%s'",
            rows_written,
            current_dataset.dataset_name,
            table_name,
        )

    except Exception as exc:
        logger.error(
            "Failed to write dataset '%s': %s", current_dataset.dataset_name, exc
        )
        existing_failures.append(
            DatasetIngestionFailure(
                dataset_name=current_dataset.dataset_name,
                error_detail=str(exc),
            )
        )

    return {
        "ingestion_results": existing_results,
        "ingestion_failures": existing_failures,
        "current_dataset_index": current_index + 1,
    }
