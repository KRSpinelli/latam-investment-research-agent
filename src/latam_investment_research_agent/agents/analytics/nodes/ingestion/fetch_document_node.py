"""Ingestion graph node: fetch document content.

Fetches the raw text content of the source document (PDF or HTML) and writes
it into the graph state.  On failure, writes to the ``error`` state field so
that the graph can route directly to the summary node.
"""

from __future__ import annotations

import logging

from latam_investment_research_agent.agents.analytics.models.ingestion_state import IngestionState
from latam_investment_research_agent.agents.analytics.services.document_fetcher import (
    DocumentFetchError,
    fetch_document,
)

logger = logging.getLogger(__name__)


async def fetch_document_node(state: IngestionState) -> dict[str, object]:
    """Fetch raw content from the source document URL or file path.

    Invokes ``fetch_document`` with the ``source_reference`` from state.  On
    success, writes ``raw_content`` with the extracted text.  On any failure,
    writes ``error`` with the exception message and ``raw_content`` as ``None``
    so downstream nodes can detect the failure.

    Args:
        state: The current ingestion graph state.  Must contain ``source_reference``.

    Returns:
        A dict with ``raw_content`` (str or None) and optionally ``error`` (str).
    """
    source_reference: str = state["source_reference"]
    logger.info("Fetching document: %s", source_reference)

    try:
        raw_content = await fetch_document(source_reference)
        logger.info("Successfully fetched %d characters from '%s'", len(raw_content), source_reference)
        return {"raw_content": raw_content}
    except DocumentFetchError as exc:
        logger.error("Failed to fetch document '%s': %s", source_reference, exc)
        return {"raw_content": None, "error": str(exc)}
    except Exception as exc:
        logger.error("Unexpected error fetching '%s': %s", source_reference, exc)
        return {"raw_content": None, "error": f"Unexpected error: {exc}"}
