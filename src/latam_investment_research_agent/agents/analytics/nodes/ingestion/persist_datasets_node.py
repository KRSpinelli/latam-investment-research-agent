"""Ingestion graph node: route and persist all extracted datasets in parallel.

Replaces the sequential route_dataset / write_to_clickhouse loop.  Performs one
schema introspection, parallel LLM routing, parallel DDL, and parallel bulk inserts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.models.domain import (
    ColumnDefinition,
    DatasetIngestionFailure,
    DatasetIngestionResult,
    ExtractedDataset,
    RoutingDecision,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.nodes.ingestion.write_to_clickhouse_node import (
    _determine_table_name,
)
from latam_investment_research_agent.agents.analytics.repositories.clickhouse_repository import (
    alter_tables_parallel,
    create_tables_parallel,
    insert_rows_deduplicated,
)
from latam_investment_research_agent.agents.analytics.repositories.row_preparation import (
    merge_schema_with_row_keys,
    normalize_rows,
)
from latam_investment_research_agent.agents.analytics.repositories.schema_repository import (
    get_all_table_schemas,
)
from latam_investment_research_agent.agents.analytics.services.table_router import route_dataset

logger = logging.getLogger(__name__)


async def _write_dataset(
    clickhouse_client: Any,
    dataset: ExtractedDataset,
    routing_decision: RoutingDecision,
    source_reference: str,
) -> DatasetIngestionResult:
    """Write one dataset to ClickHouse after DDL has been applied.

    Args:
        clickhouse_client: An async clickhouse_connect client instance.
        dataset: The extracted dataset to persist.
        routing_decision: Routing decision for this dataset.
        source_reference: URL or file path of the source document.

    Returns:
        A ``DatasetIngestionResult`` describing the write outcome.
    """
    table_name = _determine_table_name(routing_decision, dataset.dataset_name)
    rows_written = await insert_rows_deduplicated(
        clickhouse_client,
        table_name,
        dataset.rows,
        source_reference,
    )
    logger.info(
        "Wrote %d rows for dataset '%s' to table '%s'",
        rows_written,
        dataset.dataset_name,
        table_name,
    )
    return DatasetIngestionResult(
        dataset_name=dataset.dataset_name,
        target_table_name=table_name,
        routing_action=routing_decision.routing_action,
        rows_written=rows_written,
    )


async def persist_datasets_node(
    state: IngestionState,
    llm: BaseChatModel,
    clickhouse_client: Any,
) -> dict[str, Any]:
    """Route and persist all extracted datasets using parallel I/O.

    Phases:
    1. Introspect ClickHouse schemas once.
    2. Route all datasets concurrently against that snapshot.
    3. Apply create/alter DDL concurrently.
    4. Insert rows for each dataset concurrently.

    Routing failures and write failures are captured in ``ingestion_failures``
    without aborting sibling datasets.

    Args:
        state: The current ingestion graph state.
        llm: A ``BaseChatModel`` instance injected by the graph factory.
        clickhouse_client: An async clickhouse_connect client instance.

    Returns:
        A dict with ``ingestion_results`` and ``ingestion_failures``.
    """
    extracted_datasets = state.get("extracted_datasets", [])
    source_reference: str = state["source_reference"]

    if not extracted_datasets:
        return {"ingestion_results": [], "ingestion_failures": []}

    logger.info("Persisting %d dataset(s) in parallel", len(extracted_datasets))

    existing_schemas = await get_all_table_schemas(clickhouse_client)

    routing_outcomes = await asyncio.gather(
        *[
            route_dataset(dataset, existing_schemas, llm)
            for dataset in extracted_datasets
        ],
        return_exceptions=True,
    )

    ingestion_results: list[DatasetIngestionResult] = []
    ingestion_failures: list[DatasetIngestionFailure] = []
    routed_items: list[tuple[ExtractedDataset, RoutingDecision]] = []

    for dataset, outcome in zip(extracted_datasets, routing_outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.error("Failed to route dataset '%s': %s", dataset.dataset_name, outcome)
            ingestion_failures.append(
                DatasetIngestionFailure(
                    dataset_name=dataset.dataset_name,
                    error_detail=str(outcome),
                )
            )
            continue
        routed_items.append((dataset, outcome))

    create_specs_by_table: dict[str, list[ColumnDefinition]] = {}
    alter_specs: list[tuple[str, list[ColumnDefinition]]] = []

    for dataset, routing_decision in routed_items:
        table_name = _determine_table_name(routing_decision, dataset.dataset_name)
        normalized_rows = normalize_rows(dataset.rows)
        if routing_decision.routing_action == "create" and routing_decision.proposed_schema:
            create_specs_by_table[table_name] = merge_schema_with_row_keys(
                routing_decision.proposed_schema,
                normalized_rows,
            )
        elif routing_decision.routing_action == "append" and routing_decision.proposed_schema:
            alter_specs.append(
                (
                    table_name,
                    merge_schema_with_row_keys(
                        routing_decision.proposed_schema,
                        normalized_rows,
                    ),
                )
            )
        elif routing_decision.routing_action == "append":
            alter_specs.append(
                (
                    table_name,
                    merge_schema_with_row_keys([], normalized_rows),
                )
            )

    create_specs = list(create_specs_by_table.items())
    if create_specs:
        logger.info("Creating %d table(s) in parallel", len(create_specs))
        await create_tables_parallel(clickhouse_client, create_specs)
    if alter_specs:
        logger.info("Altering %d table(s) in parallel", len(alter_specs))
        await alter_tables_parallel(clickhouse_client, alter_specs)

    write_outcomes = await asyncio.gather(
        *[
            _write_dataset(clickhouse_client, dataset, routing_decision, source_reference)
            for dataset, routing_decision in routed_items
        ],
        return_exceptions=True,
    )

    for (dataset, _), outcome in zip(routed_items, write_outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.error("Failed to write dataset '%s': %s", dataset.dataset_name, outcome)
            ingestion_failures.append(
                DatasetIngestionFailure(
                    dataset_name=dataset.dataset_name,
                    error_detail=str(outcome),
                )
            )
        else:
            ingestion_results.append(outcome)

    logger.info(
        "Persist complete: %d succeeded, %d failed",
        len(ingestion_results),
        len(ingestion_failures),
    )

    return {
        "ingestion_results": ingestion_results,
        "ingestion_failures": ingestion_failures,
    }
