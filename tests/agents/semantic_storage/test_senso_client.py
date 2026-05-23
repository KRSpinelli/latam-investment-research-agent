"""Tests for SensoClient duplicate-ingest handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from latam_investment_research_agent.agents.semantic_storage.client import SensoClient


@pytest.mark.asyncio
async def test_kb_create_raw_updates_on_409_conflict() -> None:
    """HTTP 409 should refresh existing raw content instead of failing."""
    client = SensoClient(api_key="test-key")
    conflict_response = httpx.Response(
        status_code=409,
        request=httpx.Request("POST", "https://apiv2.senso.ai/api/v1/org/kb/raw"),
    )

    with (
        patch.object(
            client,
            "_post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Conflict",
                request=conflict_response.request,
                response=conflict_response,
            ),
        ),
        patch.object(
            client,
            "_find_child_by_title",
            new_callable=AsyncMock,
            return_value={"kb_node_id": "node_existing", "name": "My Doc"},
        ),
        patch.object(
            client,
            "kb_update_raw",
            new_callable=AsyncMock,
            return_value={"content": {"processing_status": "processing"}},
        ) as update_mock,
    ):
        result = await client.kb_create_raw(
            title="My Doc",
            text="updated body",
            folder_id="folder_1",
        )

    update_mock.assert_awaited_once_with("node_existing", "updated body")
    assert result["kb_node_id"] == "node_existing"
    assert result["reused_existing"] is True
