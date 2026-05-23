"""Report PDF filename helpers (rendering lives in agents.report.pdf_renderer)."""

from __future__ import annotations

import re


def report_pdf_filename(query: str) -> str:
    """Derive a filesystem-safe PDF filename from the research query.

    Args:
        query: Research question text.

    Returns:
        Filename ending in ``.pdf``.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", query.lower()).strip("-")
    slug = slug[:60] if slug else "research-report"
    return f"{slug}.pdf"
