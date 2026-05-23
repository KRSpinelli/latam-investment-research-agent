"""Tests for Senso ingestion error recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from latam_investment_research_agent.agents.semantic_storage.ingest import FilingMetadata
from latam_investment_research_agent.services.semantic_storage_ingestion import (
    ingest_source_to_senso,
)


@pytest.mark.asyncio
async def test_ingest_source_recovers_node_id_from_senso_400_url() -> None:
    """A 400 on the raw update URL should still return the existing node id."""
    metadata = FilingMetadata(
        ticker="",
        filing_type="NEWS",
        fiscal_year=2024,
        source_url="https://anba.com.br/article",
    )
    node_id = "9f5bcdeb-a419-45f1-b959-56b9eee27d49"
    error = httpx.HTTPStatusError(
        "Bad Request",
        request=httpx.Request(
            "PUT",
            f"https://apiv2.senso.ai/api/v1/org/kb/nodes/{node_id}/raw",
        ),
        response=httpx.Response(400),
    )

    with patch(
        "latam_investment_research_agent.services.semantic_storage_ingestion.ingest_from_url",
        new_callable=AsyncMock,
        side_effect=error,
    ):
        result = await ingest_source_to_senso(
            "https://anba.com.br/article",
            metadata,
            folder_map={"GENERAL": "folder-1"},
            client=AsyncMock(),
        )

    assert result.kb_node_id == node_id
    assert result.error is None
    assert result.processing_status == "reused_existing"
