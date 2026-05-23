"""
Search interface for the orchestrator agent.

The orchestrator calls search_memory() to retrieve grounded context from
Senso before generating investment briefs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import SensoClient
from .companies import BY_SECTOR, BY_TICKER, SECTORS


@dataclass
class SearchResult:
    content: str
    title: str
    score: float
    metadata: dict[str, Any]

    @property
    def ticker(self) -> str:
        return str(self.metadata.get("ticker", ""))

    @property
    def period(self) -> str:
        return str(self.metadata.get("period", ""))

    @property
    def filing_type(self) -> str:
        return str(self.metadata.get("filing_type", ""))

    def __str__(self) -> str:
        return (
            f"[{self.ticker} | {self.filing_type} {self.period} | score={self.score:.3f}]\n"
            f"{self.content}"
        )


async def search_memory(
    query: str,
    *,
    ticker: str | None = None,
    sector: str | None = None,
    filing_type: str | None = None,
    fiscal_year: int | None = None,
    top_k: int = 8,
    client: SensoClient | None = None,
) -> list[SearchResult]:
    """
    Semantic search over the Senso KB.

    Args:
        query:       Natural language question from the orchestrator.
        ticker:      Narrow to one company, e.g. "RAIL3".
        sector:      Narrow to a sector: "logistics" | "agriculture" | "energy".
        filing_type: Narrow to "FR" or "DFT".
        fiscal_year: Narrow to a specific year, e.g. 2024.
        top_k:       Max results to return.

    Returns a list of SearchResult ordered by relevance score.
    """
    c = client or SensoClient()

    # Resolve folder prefix from ticker/sector hint
    folder_prefix = "latam-alpha"
    if ticker:
        company = BY_TICKER.get(ticker.upper())
        if company:
            slug = f"{ticker.upper()}-{company.name.replace(' ', '')}"
            folder_prefix = f"latam-alpha/{company.sector}/{slug}"
    elif sector:
        if sector.lower() not in SECTORS:
            raise ValueError(f"Unknown sector {sector!r}. Choose from: {SECTORS}")
        folder_prefix = f"latam-alpha/{sector.lower()}"

    # Metadata filters
    filters: dict[str, Any] = {}
    if filing_type:
        filters["filing_type"] = filing_type.upper()
    if fiscal_year:
        filters["fiscal_year"] = fiscal_year

    raw = await c.search(query, folder_prefix=folder_prefix, top_k=top_k, filters=filters or None)

    return [
        SearchResult(
            content=r.get("content", ""),
            title=r.get("title", ""),
            score=float(r.get("score", 0.0)),
            metadata=r.get("metadata", {}),
        )
        for r in raw
    ]


async def search_sector_comparison(
    query: str,
    sector: str,
    fiscal_year: int | None = None,
    top_k_per_company: int = 3,
    client: SensoClient | None = None,
) -> dict[str, list[SearchResult]]:
    """
    Fan-out search across every company in a sector.
    Returns a dict keyed by ticker, useful for cross-company comparisons.
    """
    companies = BY_SECTOR.get(sector.lower(), [])
    if not companies:
        raise ValueError(f"Unknown sector {sector!r}. Choose from: {SECTORS}")

    c = client or SensoClient()
    results: dict[str, list[SearchResult]] = {}
    for company in companies:
        hits = await search_memory(
            query,
            ticker=company.ticker,
            fiscal_year=fiscal_year,
            top_k=top_k_per_company,
            client=c,
        )
        results[company.ticker] = hits
    return results
