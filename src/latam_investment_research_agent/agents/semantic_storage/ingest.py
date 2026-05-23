"""
Ingest CVM filing text (extracted by Nimble) into Senso KB.

Upstream contract:
  - Nimble fetches PDF from CVM/B3, extracts text, calls ingest_filing()
  - Each call corresponds to one filing document (or a logical section of it)

Chunking strategy:
  - Split on double-newlines, skip blanks, cap at MAX_CHUNK_CHARS
  - Overlap is handled by the Senso embedding layer; we keep chunks clean here
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .client import SensoClient
from .companies import BY_TICKER, kb_path

MAX_CHUNK_CHARS = 1_500
FILING_TYPES = {"FR": "Formulario de Referencia", "DFT": "Demonstracoes Financeiras Trimestrais"}


@dataclass
class FilingMetadata:
    ticker: str                   # e.g. "RAIL3"
    filing_type: str              # "FR" | "DFT"
    fiscal_year: int              # e.g. 2024
    quarter: int | None = None    # 1-4 for DFT; None for FR
    source_url: str = ""          # original CVM URL
    language: str = "pt-BR"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def period_label(self) -> str:
        if self.quarter:
            return f"{self.fiscal_year}Q{self.quarter}"
        return str(self.fiscal_year)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "filing_type": self.filing_type,
            "filing_type_label": FILING_TYPES.get(self.filing_type, self.filing_type),
            "fiscal_year": self.fiscal_year,
            "quarter": self.quarter,
            "period": self.period_label,
            "source_url": self.source_url,
            "language": self.language,
            **self.extra,
        }


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split filing text into KB-sized chunks."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            # paragraph itself exceeds limit — hard-split it
            while len(para) > max_chars:
                chunks.append(para[:max_chars])
                para = para[max_chars:]
            current = para
    if current:
        chunks.append(current)
    return chunks


async def ingest_filing(
    text: str,
    metadata: FilingMetadata,
    client: SensoClient | None = None,
) -> list[dict[str, Any]]:
    """
    Chunk and store a CVM filing in Senso KB.

    Returns list of upsert responses from Senso (one per chunk).
    """
    c = client or SensoClient()

    company = BY_TICKER.get(metadata.ticker)
    if not company:
        raise ValueError(f"Unknown ticker {metadata.ticker!r} — add it to companies.py first")

    folder = kb_path(company)
    chunks = _chunk_text(text)
    meta = metadata.to_dict()

    results: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        doc = {
            "content": chunk,
            "title": f"{metadata.ticker} {metadata.filing_type} {metadata.period_label} — chunk {i + 1}/{len(chunks)}",
            "metadata": {**meta, "chunk_index": i, "chunk_total": len(chunks)},
        }
        resp = await c.upsert_document(folder, doc)
        results.append(resp)

    return results
