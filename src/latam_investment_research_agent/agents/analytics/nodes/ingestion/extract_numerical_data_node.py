"""Ingestion graph node: extract numerical datasets from raw document text.

Calls the numerical extraction service and initialises the dataset loop index.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from latam_investment_research_agent.agents.analytics.models.domain import ExtractedDataset
from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.services.numerical_extractor import (
    extract_datasets,
)

logger = logging.getLogger(__name__)


async def extract_numerical_data_node(
    state: IngestionState,
    llm: BaseChatModel,
) -> dict[str, Any]:
    """Extract all numerical datasets from the document text stored in state.

    If ``raw_content`` is ``None`` (set by the fetch node on failure), returns
    empty datasets immediately without invoking the LLM.

    Args:
        state: The current ingestion graph state.  Must contain ``raw_content``.
        llm: A ``BaseChatModel`` instance injected by the graph factory.

    Returns:
        A dict with ``extracted_datasets`` (list[ExtractedDataset]).
    """
    raw_content: str | None = state.get("raw_content")

    if raw_content is None:
        logger.warning("raw_content is None; skipping extraction.")
        return {"extracted_datasets": []}

    extracted_datasets: list[ExtractedDataset] = await extract_datasets(raw_content, llm)
    logger.info("Extracted %d datasets from document.", len(extracted_datasets))

    return {"extracted_datasets": extracted_datasets}
