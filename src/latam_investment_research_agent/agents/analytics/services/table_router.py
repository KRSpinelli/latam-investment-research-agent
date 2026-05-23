"""LLM-based table routing service.

For each extracted dataset, the router queries the LLM with the dataset's
metadata and all existing ClickHouse table schemas.  The LLM returns a
``RoutingDecision`` indicating whether to append to an existing table or
create a new one.

Cross-language routing (Portuguese dataset labels → English table names) is
handled naturally by the LLM without any special-case logic.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.constants import (
    CREATE_NEW_TABLE_SENTINEL,
    MANDATORY_AUDIT_COLUMNS,
)
from latam_investment_research_agent.agents.analytics.models.domain import (
    ExtractedDataset,
    RoutingDecision,
    TableSchema,
)

logger = logging.getLogger(__name__)

_ROUTING_SYSTEM_PROMPT = f"""You are a database architect responsible for routing financial
datasets into a ClickHouse analytical database.

Given a new dataset (name, context labels, and column names) and a list of existing table
schemas, decide whether the new dataset belongs in an existing table or requires a new table.

RULES:
1. If the dataset is semantically equivalent to an existing table (same category of financial
   data, compatible columns), return routing_action="append" with the existing table name.
2. If no existing table is a good match, return routing_action="create" with
   target_table_name="{CREATE_NEW_TABLE_SENTINEL}" and a proposed_schema listing the data
   columns.
3. proposed_schema MUST NOT include these reserved audit columns:
   {", ".join(MANDATORY_AUDIT_COLUMNS)}
4. Column names in proposed_schema MUST be snake_case with no abbreviations.
5. Use Decimal(18,4) for monetary values, Float64 for ratios/percentages, String for text,
   UInt16 or UInt32 for years/counts.
6. Consider cross-language equivalence: Portuguese labels may match English table names."""


def _build_routing_prompt(
    dataset: ExtractedDataset,
    existing_schemas: list[TableSchema],
) -> str:
    """Build the user message for the LLM routing call.

    Args:
        dataset: The extracted dataset to route.
        existing_schemas: All current ClickHouse table schemas.

    Returns:
        A formatted string describing the dataset and available tables.
    """
    schema_descriptions: list[str] = []
    for schema in existing_schemas:
        column_summary = ", ".join(
            f"{column.column_name} ({column.column_type})" for column in schema.columns
        )
        schema_descriptions.append(f"  - {schema.table_name}: [{column_summary}]")

    existing_tables_text = (
        "\n".join(schema_descriptions) if schema_descriptions else "  (no existing tables)"
    )

    return (
        f"Dataset to route:\n"
        f"  Name: {dataset.dataset_name}\n"
        f"  Context labels: {', '.join(dataset.context_labels)}\n"
        f"  Columns: {', '.join(dataset.column_names)}\n"
        f"  Row count: {len(dataset.rows)}\n\n"
        f"Existing ClickHouse tables:\n{existing_tables_text}"
    )


def _validate_proposed_schema_has_no_audit_columns(decision: RoutingDecision) -> None:
    """Raise ValueError if the proposed schema contains reserved audit column names.

    Args:
        decision: The routing decision returned by the LLM.

    Raises:
        ValueError: If any column in ``decision.proposed_schema`` uses a reserved
            audit column name.
    """
    if decision.proposed_schema is None:
        return

    for column_definition in decision.proposed_schema:
        if column_definition.column_name in MANDATORY_AUDIT_COLUMNS:
            raise ValueError(
                f"LLM proposed reserved audit column '{column_definition.column_name}' "
                "in the new table schema.  Audit columns are managed by the repository "
                "and must not appear in proposed_schema."
            )


async def route_dataset(
    dataset: ExtractedDataset,
    existing_schemas: list[TableSchema],
    llm: BaseChatModel,
) -> RoutingDecision:
    """Determine the ClickHouse destination for one extracted dataset.

    Passes the dataset metadata and all existing table schemas to the LLM and
    returns a ``RoutingDecision`` indicating whether to append to an existing
    table or create a new one.

    Args:
        dataset: The extracted dataset to route.
        existing_schemas: All current ClickHouse table schemas, as returned by
            ``get_all_table_schemas``.
        llm: A ``BaseChatModel`` instance, received via dependency injection.

    Returns:
        A ``RoutingDecision`` with ``routing_action`` set to ``"append"`` or
        ``"create"``.  When ``"create"``, ``proposed_schema`` contains the
        column definitions for the new table.

    Raises:
        ValueError: If the LLM proposes a ``proposed_schema`` that includes any
            reserved audit column name.

    Example:
        decision = await route_dataset(dataset, schemas, llm_provider)
        if decision.routing_action == "create":
            await repo.create_table(client, "new_table", decision.proposed_schema)
    """
    logger.info(
        "Routing dataset '%s' (%d rows, columns: %s) against %d existing table(s)",
        dataset.dataset_name,
        len(dataset.rows),
        ", ".join(dataset.column_names),
        len(existing_schemas),
    )
    if existing_schemas:
        logger.debug(
            "Existing tables: %s",
            ", ".join(s.table_name for s in existing_schemas),
        )

    structured_llm = llm.with_structured_output(RoutingDecision)
    user_message = _build_routing_prompt(dataset, existing_schemas)

    messages = [
        {"role": "system", "content": _ROUTING_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    decision: RoutingDecision = await structured_llm.ainvoke(messages)

    _validate_proposed_schema_has_no_audit_columns(decision)

    if decision.routing_action == "create":
        proposed_cols = (
            ", ".join(c.column_name for c in decision.proposed_schema)
            if decision.proposed_schema
            else "none"
        )
        logger.info(
            "Routing decision for '%s': CREATE new table — proposed columns: %s",
            dataset.dataset_name,
            proposed_cols,
        )
    else:
        logger.info(
            "Routing decision for '%s': APPEND to existing table '%s'",
            dataset.dataset_name,
            decision.target_table_name,
        )
    logger.debug("Routing rationale: %s", decision.rationale)
    return decision
