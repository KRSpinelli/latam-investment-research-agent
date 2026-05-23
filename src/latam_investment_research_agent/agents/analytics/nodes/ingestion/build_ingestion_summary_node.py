"""Ingestion graph node: build the final ingestion summary.

The terminal node in the ingestion graph.  Compiles the accumulated results
and failures into an ``IngestionSummary`` returned to the parent orchestrator.
"""

from __future__ import annotations

import logging
from typing import Any

from latam_investment_research_agent.agents.analytics.models.domain import (
    DatasetIngestionFailure,
    DatasetIngestionResult,
)
from latam_investment_research_agent.agents.analytics.models.ingestion_state import (
    IngestionState,
    IngestionSummary,
)

logger = logging.getLogger(__name__)


async def build_ingestion_summary_node(state: IngestionState) -> dict[str, Any]:
    """Compile the ingestion summary from accumulated state.

    Reads ``ingestion_results``, ``ingestion_failures``, and
    ``extracted_datasets`` from state to produce an ``IngestionSummary``.
    Handles the case where the fetch node failed (empty datasets list).

    Args:
        state: The final ingestion graph state after all datasets have been
            processed (or after a fatal fetch failure).

    Returns:
        A dict with ``ingestion_summary`` containing the compiled result.
    """
    source_reference: str = state.get("source_reference", "")
    extracted_datasets = state.get("extracted_datasets", [])
    ingestion_results: list[DatasetIngestionResult] = list(state.get("ingestion_results", []))
    ingestion_failures: list[DatasetIngestionFailure] = list(state.get("ingestion_failures", []))

    summary: IngestionSummary = {
        "source_reference": source_reference,
        "total_datasets_found": len(extracted_datasets),
        "datasets_succeeded": ingestion_results,
        "datasets_failed": ingestion_failures,
    }

    logger.info(
        "Ingestion complete for '%s': %d succeeded, %d failed",
        source_reference,
        len(ingestion_results),
        len(ingestion_failures),
    )

    return {"ingestion_summary": summary}
