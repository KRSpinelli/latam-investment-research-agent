"""
Search interface for the orchestrator agent.

The orchestrator calls search_memory() to retrieve grounded chunks from Senso
before generating investment briefs. Chunks come back without AI synthesis —
feed them directly into your own LLM prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import SensoClient


@dataclass
class Chunk:
    content: str
    title: str
    score: float
    content_id: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"[{self.title} | score={self.score:.3f}]\n{self.content}"


def _parse_chunks(raw: list[dict[str, Any]]) -> list[Chunk]:
    return [
        Chunk(
            content=r.get("chunk_text", r.get("text", "")),
            title=r.get("title", ""),
            score=float(r.get("score", r.get("relevance_score", 0.0))),
            content_id=str(r.get("content_id", r.get("kb_content_id", ""))),
            metadata=r.get("metadata", {}),
        )
        for r in raw
    ]


async def search_memory(
    query: str,
    *,
    content_ids: list[str] | None = None,
    max_results: int = 8,
    client: SensoClient | None = None,
) -> list[Chunk]:
    """
    Semantic search over the Senso KB. Returns ranked chunks for grounding.

    Args:
        query:       Natural-language question from the orchestrator.
        content_ids: Optional list of KB content node IDs to restrict the search.
                     Get these from a prior ingest_filing() call (node["kb_node_id"]).
        max_results: Max chunks returned (capped at 20 by Senso).

    Returns chunks ordered by relevance score.
    """
    c = client or SensoClient()
    raw = await c.search_context(
        query=query,
        max_results=max_results,
        content_ids=content_ids,
    )
    return _parse_chunks(raw)


async def search_for_brief(
    topic: str,
    content_ids: list[str] | None = None,
    max_results: int = 12,
    client: SensoClient | None = None,
) -> str:
    """
    Convenience wrapper: returns a single grounded context block ready to
    inject into the orchestrator's LLM prompt.
    """
    chunks = await search_memory(
        topic, content_ids=content_ids, max_results=max_results, client=client
    )
    if not chunks:
        return "No relevant sources found in the knowledge base."
    return "\n\n---\n\n".join(str(c) for c in chunks)
