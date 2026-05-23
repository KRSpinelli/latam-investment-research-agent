"""Nimble agent — web search, crawling, and scraping via Nimble API."""

from __future__ import annotations

import logging
from typing import Protocol

from latam_investment_research_agent.agents.nimble.client import NimbleClient
from latam_investment_research_agent.agents.nimble.config import get_nimble_settings
from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument

logger = logging.getLogger(__name__)


class NimbleAgent(Protocol):
    def acquire(
        self,
        query: str,
        *,
        max_results: int = 8,
        seed_urls: list[str] | None = None,
    ) -> list[NimbleDocument]: ...


def _dedupe_documents(documents: list[NimbleDocument]) -> list[NimbleDocument]:
    seen: set[str] = set()
    out: list[NimbleDocument] = []
    for doc in documents:
        key = doc.final_url.rstrip("/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out


class NimbleWebAgent:
    """
    Discovers and fetches documents via Nimble search + extract.

    Search covers open-web discovery; seed URLs are extracted directly so
    PDFs, wikis, and other formats are captured as raw payloads.
    """

    def __init__(self, client: NimbleClient) -> None:
        self._client = client

    @property
    def _search_depth(self) -> str:
        return self._client.settings.search_depth

    def acquire(
        self,
        query: str,
        *,
        max_results: int = 8,
        seed_urls: list[str] | None = None,
    ) -> list[NimbleDocument]:
        documents: list[NimbleDocument] = []

        search_query = query.strip()
        if "brazil" not in search_query.lower() and "brasil" not in search_query.lower():
            search_query = f"{search_query} Brazil"

        documents.extend(self._client.search(search_query, max_results=max_results))

        seed_set = {u.rstrip("/").lower() for u in (seed_urls or [])}
        found_urls = {d.final_url.rstrip("/").lower() for d in documents if d.ok}
        for url in seed_urls or []:
            if url.rstrip("/").lower() not in found_urls:
                documents.append(
                    self._client.extract_url(url, discovery_source="seed_url")
                )

        # Deep search already returns page content; only extract lite/fast hits.
        if self._search_depth not in {"deep"}:
            for doc in list(documents):
                if doc.ok and not doc.raw_body and doc.url:
                    if doc.url.rstrip("/").lower() not in seed_set:
                        documents.append(
                            self._client.extract_url(doc.url, discovery_source="extract")
                        )

        return _dedupe_documents(documents)[:max_results]


def get_nimble_agent() -> NimbleAgent:
    settings = get_nimble_settings()
    if not settings.api_key:
        logger.warning("NIMBLE_API_KEY not set — web acquisition will fail until configured")
    return NimbleWebAgent(NimbleClient(settings))
