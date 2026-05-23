"""Senso KB ingestion for research document URLs."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from latam_investment_research_agent.agents.retrieval.schemas.market_signal import (
    MarketSignal,
)
from latam_investment_research_agent.agents.semantic_storage.client import SensoClient
from latam_investment_research_agent.agents.semantic_storage.companies import COMPANIES
from latam_investment_research_agent.agents.semantic_storage.ingest import (
    FilingMetadata,
    ingest_from_url,
)
from latam_investment_research_agent.agents.semantic_storage.kb_scaffold import (
    FolderMap,
    scaffold_kb,
)
from latam_investment_research_agent.schemas.research import (
    ResearchResponse,
    SensoIngestionResultResponse,
)

logger = logging.getLogger(__name__)

_SENSO_NODE_ID_IN_ERROR = re.compile(
    r"/org/kb/nodes/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/raw",
    re.IGNORECASE,
)

_HOST_LABEL_TO_TICKER: dict[str, str] = {
    "cooxupe": "COOXUPE",
}


def _signal_for_url(url: str, signals: list[MarketSignal]) -> MarketSignal | None:
    normalized = url.rstrip("/").lower()
    for signal in signals:
        if signal.url.rstrip("/").lower() == normalized:
            return signal
    return None


def _ticker_from_company_name(company_name: str) -> str | None:
    name_lower = company_name.strip().lower()
    for company in COMPANIES:
        if company.name.lower() == name_lower:
            return company.ticker
    return None


def _infer_ticker(url: str, signal: MarketSignal | None) -> str:
    """Infer an optional company ticker for folder routing and document titles.

    Unknown or missing tickers route to the general ``research`` folder in Senso.
    """
    if signal is not None:
        if signal.tickers:
            return signal.tickers[0]
        for company_name in signal.companies:
            ticker = _ticker_from_company_name(company_name)
            if ticker is not None:
                return ticker

    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    host_label = host.split(".")[0]
    return _HOST_LABEL_TO_TICKER.get(host_label) or ""


def _infer_filing_type(url: str, signal: MarketSignal | None) -> str:
    url_lower = url.lower()
    if url_lower.endswith(".pdf"):
        if any(token in url_lower for token in ("sustainab", "esg", "relatorio")):
            return "SR"
        if "referencia" in url_lower:
            return "FR"
        if "demonstrac" in url_lower or "trimestral" in url_lower:
            return "DFT"
        return "SR"
    if signal is not None and signal.source_type in {"company_report", "company_reports"}:
        return "SR"
    return "NEWS"


def _infer_fiscal_year(signal: MarketSignal | None) -> int:
    if signal is not None and signal.crawled_at is not None:
        return signal.crawled_at.year
    return datetime.now(tz=UTC).year


def build_filing_metadata(
    source_reference: str,
    research: ResearchResponse,
) -> FilingMetadata:
    """Build Senso filing metadata for a research document URL.

    Args:
        source_reference: Document URL from the research pipeline.
        research: Completed research response including market signals.

    Returns:
        Filing metadata for ingestion. Documents without a company ticker use
        the general ``research`` folder in Senso.
    """
    signal = _signal_for_url(source_reference, research.signals)
    return FilingMetadata(
        ticker=_infer_ticker(source_reference, signal),
        filing_type=_infer_filing_type(source_reference, signal),
        fiscal_year=_infer_fiscal_year(signal),
        source_url=source_reference,
    )


async def ingest_source_to_senso(
    source_reference: str,
    metadata: FilingMetadata,
    *,
    folder_map: FolderMap,
    client: SensoClient,
) -> SensoIngestionResultResponse:
    """Fetch a URL and ingest its full text into the Senso KB.

    Args:
        source_reference: PDF or web page URL to ingest.
        metadata: Filing context for folder routing and document title.
        folder_map: Pre-built ticker → folder_id map.
        client: Shared Senso API client.

    Returns:
        Per-URL ingestion outcome (success fields or ``error``).
    """
    title = metadata.document_title()
    try:
        result = await ingest_from_url(
            url=source_reference,
            metadata=metadata,
            folder_map=folder_map,
            client=client,
        )
        content = result.get("content") or {}
        return SensoIngestionResultResponse(
            source_reference=source_reference,
            ticker=metadata.ticker,
            filing_type=metadata.filing_type,
            fiscal_year=metadata.fiscal_year,
            title=title,
            kb_node_id=result.get("kb_node_id") or result.get("content_id"),
            processing_status=content.get("processing_status"),
        )
    except Exception as exc:
        error_text = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            error_text = f"{exc.request.url} {error_text}"
        node_match = _SENSO_NODE_ID_IN_ERROR.search(error_text)
        if node_match is not None:
            node_id = node_match.group(1)
            logger.info(
                "Senso document already exists for %s; reusing node %s",
                source_reference,
                node_id,
            )
            return SensoIngestionResultResponse(
                source_reference=source_reference,
                ticker=metadata.ticker,
                filing_type=metadata.filing_type,
                fiscal_year=metadata.fiscal_year,
                title=title,
                kb_node_id=node_id,
                processing_status="reused_existing",
            )
        logger.warning("Senso ingestion failed for %s: %s", source_reference, exc)
        return SensoIngestionResultResponse(
            source_reference=source_reference,
            ticker=metadata.ticker,
            filing_type=metadata.filing_type,
            fiscal_year=metadata.fiscal_year,
            title=title,
            error=str(exc),
        )


async def ingest_sources_to_senso(
    source_references: list[str],
    research: ResearchResponse,
) -> list[SensoIngestionResultResponse]:
    """Ingest each source URL into Senso in parallel.

    Args:
        source_references: Unique document URLs to ingest.
        research: Research output used to infer filing metadata per URL.

    Returns:
        One result per URL (skipped URLs include an ``error`` explaining why).
    """
    if not source_references:
        return []

    client = SensoClient()
    folder_map = await scaffold_kb(client)

    async def _ingest_one(source_reference: str) -> SensoIngestionResultResponse:
        metadata = build_filing_metadata(source_reference, research)
        return await ingest_source_to_senso(
            source_reference,
            metadata,
            folder_map=folder_map,
            client=client,
        )

    tasks = [
        asyncio.create_task(_ingest_one(source_reference))
        for source_reference in source_references
    ]
    return list(await asyncio.gather(*tasks))
