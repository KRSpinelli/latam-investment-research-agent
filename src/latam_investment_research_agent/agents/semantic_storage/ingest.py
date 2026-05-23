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
from urllib.parse import urlparse

from .client import SensoClient
from .document_fetch import fetch_text_from_url
from .kb_scaffold import GENERAL_FOLDER_KEY, FolderMap, scaffold_kb

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
        """Build a Senso KB title unique per source URL when ``source_url`` is set."""
        subject = self.ticker if self.ticker else "Market research"
        base_title = f"{subject} — {self.filing_type_label} {self.period_label}"
        if not self.source_url:
            return base_title
        return f"{base_title} — {_title_slug_from_url(self.source_url)}"


def _title_slug_from_url(url: str, maximum_length: int = 72) -> str:
    """Derive a short, human-readable slug from a URL for document titles.

    Args:
        url: Source document URL.
        maximum_length: Maximum slug length before truncation.

    Returns:
        Slug such as ``example.com/my-article``.
    """
    parsed = urlparse(url)
    host = parsed.netloc
    if host.startswith("www."):
        host = host[4:]
    path_segment = parsed.path.rstrip("/").split("/")[-1]
    slug = f"{host}/{path_segment}" if path_segment else host
    if len(slug) > maximum_length:
        return f"{slug[: maximum_length - 3]}..."
    return slug


def _resolve_folder_id(folder_map: FolderMap, ticker: str) -> str:
    """Pick a company folder when registered, otherwise the general research folder.

    Args:
        folder_map: Map of ticker (or ``GENERAL``) to Senso folder node IDs.
        ticker: Optional company ticker from metadata.

    Returns:
        Senso KB folder node ID to receive the document.

    Raises:
        KeyError: If neither a matching ticker folder nor the general folder exists.
    """
    if ticker and ticker in folder_map:
        return folder_map[ticker]
    general_folder_id = folder_map.get(GENERAL_FOLDER_KEY)
    if general_folder_id:
        return general_folder_id
    raise KeyError(
        f"No KB folder for ticker {ticker!r} and no {GENERAL_FOLDER_KEY!r} folder in map"
    )


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

    if folder_map is None:
        folder_map = await scaffold_kb(c)

    folder_id = _resolve_folder_id(folder_map, metadata.ticker)

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
        KeyError: If no suitable KB folder exists in the folder map.
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
