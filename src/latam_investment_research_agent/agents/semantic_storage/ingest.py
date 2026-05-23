"""
Ingest CVM filing text (extracted by Nimble) into Senso KB.

Upstream contract:
    Nimble fetches a PDF from CVM/company website, extracts text,
    then calls ingest_filing() with the text and a FilingMetadata object.

Senso handles all chunking and embedding — we just push the raw text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .client import SensoClient
from .companies import BY_TICKER
from .document_fetch import fetch_text_from_url
from .kb_scaffold import FolderMap, scaffold_kb

FILING_TYPES = {
    "FR": "Formulario de Referencia",
    "DFT": "Demonstracoes Financeiras Trimestrais",
    "SR": "Sustainability Report",
    "NEWS": "News Article",
}


@dataclass
class FilingMetadata:
    ticker: str                     # e.g. "COOXUPE", "RAIL3"
    filing_type: str                # "FR" | "DFT" | "SR" | "NEWS"
    fiscal_year: int                # e.g. 2024
    quarter: int | None = None      # 1-4 for DFT; None for annual / SR
    source_url: str = ""
    language: str = "pt-BR"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def period_label(self) -> str:
        if self.quarter:
            return f"{self.fiscal_year}Q{self.quarter}"
        return str(self.fiscal_year)

    @property
    def filing_type_label(self) -> str:
        return FILING_TYPES.get(self.filing_type, self.filing_type)

    def document_title(self) -> str:
        return f"{self.ticker} — {self.filing_type_label} {self.period_label}"


async def ingest_filing(
    text: str,
    metadata: FilingMetadata,
    folder_map: FolderMap | None = None,
    client: SensoClient | None = None,
) -> dict[str, Any]:
    """
    Ingest a CVM filing (or news article) as raw text into the Senso KB.

    Args:
        text:       Extracted text from Nimble (or any upstream source).
        metadata:   Filing context — ticker, type, year, quarter, source URL.
        folder_map: Pre-built ticker → folder_id map from scaffold_kb().
                    If omitted, scaffold_kb() is called automatically.
        client:     Optional shared SensoClient.

    Returns the Senso KB node response dict.
    """
    c = client or SensoClient()

    if BY_TICKER.get(metadata.ticker) is None:
        raise ValueError(
            f"Unknown ticker {metadata.ticker!r} — add it to companies.py first"
        )

    if folder_map is None:
        folder_map = await scaffold_kb(c)

    folder_id = folder_map.get(metadata.ticker)
    if not folder_id:
        raise KeyError(f"No KB folder found for ticker {metadata.ticker!r}")

    return await c.kb_create_raw(
        title=metadata.document_title(),
        text=text,
        folder_id=folder_id,
    )


async def ingest_from_url(
    url: str,
    metadata: FilingMetadata,
    folder_map: FolderMap | None = None,
    client: SensoClient | None = None,
) -> dict[str, Any]:
    """Fetch a PDF or webpage, extract text, and ingest into the Senso KB.

    HTML pages use full-page text extraction (articles, reports). PDFs use
    all-page text via ``pdfplumber``. Then delegates to :func:`ingest_filing`.

    Args:
        url: Public URL of a PDF or static HTML page.
        metadata: Filing context (ticker, type, year, source URL).
        folder_map: Optional pre-built ticker → folder_id map from
            :func:`scaffold_kb`.
        client: Optional shared :class:`SensoClient`.

    Returns:
        The Senso KB node response dict from :meth:`SensoClient.kb_create_raw`.

    Raises:
        DocumentFetchError: If the URL cannot be fetched or parsed.
        ValueError: If no text could be extracted from the page.
        ValueError: If ``metadata.ticker`` is not registered in ``companies.py``.
        KeyError: If no KB folder exists for the ticker.
    """
    if not metadata.source_url:
        metadata = FilingMetadata(
            ticker=metadata.ticker,
            filing_type=metadata.filing_type,
            fiscal_year=metadata.fiscal_year,
            quarter=metadata.quarter,
            source_url=url,
            language=metadata.language,
            extra=dict(metadata.extra),
        )

    text = await fetch_text_from_url(url)
    if not text.strip():
        raise ValueError(f"No text extracted from {url!r}")

    return await ingest_filing(
        text=text,
        metadata=metadata,
        folder_map=folder_map,
        client=client,
    )
