"""Unit tests for analytics ingestion helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument
from latam_investment_research_agent.services.analytics_ingestion import (
    source_references_from_documents,
)


def _document(
    *,
    url: str,
    final_url: str | None = None,
    ok: bool = True,
) -> NimbleDocument:
    now = datetime(2026, 5, 23, 14, 0, tzinfo=UTC)
    text = "sample content" if ok else ""
    return NimbleDocument(
        url=url,
        final_url=final_url or url,
        title="title",
        text=text,
        fetched_at=now,
        error=None if ok else "fetch failed",
    )


def test_source_references_from_documents_uses_final_url_and_skips_failed() -> None:
    """Only successful documents contribute unique final URLs."""
    documents = [
        _document(url="https://example.com/a", final_url="https://example.com/a-final"),
        _document(url="https://example.com/b", ok=False),
        _document(url="https://example.com/a", final_url="https://example.com/a-final"),
    ]
    references = source_references_from_documents(documents)
    assert references == ["https://example.com/a-final"]
