"""Fetch document text from URLs for Senso KB ingestion.

Unlike the analytics document fetcher (table-focused HTML for numerical extraction),
this module extracts full page text from HTML so articles and reports retain
narrative content for semantic search.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from latam_investment_research_agent.agents.analytics.services.document_fetcher import (
    DocumentFetchError,
    _extract_text_from_pdf_bytes,
    _is_pdf_content_type,
)

logger = logging.getLogger(__name__)

_BLANK_LINE_PATTERN = re.compile(r"\n{3,}")


def _extract_full_page_text_from_html_bytes(html_bytes: bytes) -> str:
    """Extract readable text from an entire HTML page.

    Strips non-content elements, prefers ``article`` / ``main`` when present,
    then normalizes whitespace.

    Args:
        html_bytes: Raw bytes of the HTML document.

    Returns:
        Plain text suitable for Senso KB ingestion.
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag_name in ("script", "style", "noscript", "header", "footer", "nav"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    content_root = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    raw_text = content_root.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    text = "\n".join(lines)
    text = _BLANK_LINE_PATTERN.sub("\n\n", text)
    logger.info("HTML full-page extraction: ~%d characters", len(text))
    return text


async def fetch_text_from_url(url: str) -> str:
    """Fetch a URL and return full document text for Senso ingestion.

    PDFs are parsed with ``pdfplumber`` (all pages). HTML pages return full
    body text, not table cells only.

    Args:
        url: HTTP or HTTPS URL pointing to a PDF or HTML page.

    Returns:
        Extracted plain text from the document.

    Raises:
        DocumentFetchError: If the URL cannot be fetched or parsed.
        ValueError: If no text could be extracted.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must be http or https, got: {url!r}")

    logger.info("Fetching document for Senso: %s", url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as http_client:
        try:
            response = await http_client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DocumentFetchError(
                url,
                f"HTTP {exc.response.status_code} response",
            ) from exc
        except httpx.RequestError as exc:
            raise DocumentFetchError(url, f"Network error: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        url_lower = url.lower()

        if _is_pdf_content_type(content_type) or url_lower.endswith(".pdf"):
            logger.info("Detected PDF — extracting all pages")
            return _extract_text_from_pdf_bytes(response.content, url)

        logger.info("Detected HTML — extracting full page text")
        return _extract_full_page_text_from_html_bytes(response.content)
