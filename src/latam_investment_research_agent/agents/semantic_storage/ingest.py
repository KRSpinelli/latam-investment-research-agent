"""
Ingest CVM filing text (extracted by Nimble) into Senso KB.

Upstream contract:
    Nimble fetches a PDF from CVM/company website, extracts text,
    then calls ingest_filing() with the text and a FilingMetadata object.

Senso handles all chunking and embedding — we just push the raw text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .client import SensoClient
from .companies import BY_TICKER
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


def _extract_text_from_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import io
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError as e:
        raise ImportError(
            "pdfplumber is required for PDF extraction. "
            "Install with: pip install pdfplumber"
        ) from e


async def ingest_from_url(
    url: str,
    metadata: FilingMetadata,
    folder_map: FolderMap | None = None,
    client: SensoClient | None = None,
) -> dict[str, Any]:
    """
    Fetch a URL (PDF or webpage), extract its text, and ingest into Senso KB.

    This is the main entry point for teammates passing URLs from Nimble.

    Args:
        url:        Direct URL to a PDF or webpage (e.g. CVM filing, news article).
        metadata:   Filing context — ticker, type, year, etc.
                    Set source_url to the same URL if you haven't already.
        folder_map: Pre-built ticker → folder_id map. Auto-built if omitted.
        client:     Optional shared SensoClient.

    Returns the Senso KB node response dict.

    Example:
        await ingest_from_url(
            url="https://www.cooxupe.com.br/wp-content/.../relatorio.pdf",
            metadata=FilingMetadata(
                ticker="COOXUPE",
                filing_type="SR",
                fiscal_year=2024,
                source_url="https://www.cooxupe.com.br/wp-content/.../relatorio.pdf",
            ),
        )
    """
    if not metadata.source_url:
        metadata.source_url = url

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
        response = await http.get(url, headers={"User-Agent": "LatAmAlpha/1.0"})
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(response.content)
    else:
        text = _extract_text_from_html(response.text)

    if not text.strip():
        raise ValueError(f"No text could be extracted from {url!r}")

    return await ingest_filing(text, metadata, folder_map, client)
