"""Unit tests for the document fetcher service.

Covers both PDF and HTML document fetching.  All HTTP calls are mocked.
Run and confirm FAILING before implementing services/document_fetcher.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latam_investment_research_agent.agents.analytics.services.document_fetcher import (
    DocumentFetchError,
    fetch_document,
)


def _make_http_response(
    status_code: int,
    content: bytes,
    content_type: str = "application/pdf",
) -> MagicMock:
    """Build a mock httpx Response.

    Args:
        status_code: HTTP status code.
        content: Raw response body bytes.
        content_type: Value for the Content-Type header.

    Returns:
        A MagicMock simulating an httpx.Response.
    """
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    response.headers = {"content-type": content_type}
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        response.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return response


@pytest.mark.asyncio
async def test_fetch_document_returns_text_for_pdf_url() -> None:
    """fetch_document returns a non-empty string for a PDF URL."""
    pdf_bytes = b"%PDF-1.4 fake pdf content with some text"

    with patch(
        "latam_investment_research_agent.agents.analytics.services.document_fetcher"
        ".httpx.AsyncClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            return_value=_make_http_response(200, pdf_bytes, "application/pdf")
        )

        with patch(
            "latam_investment_research_agent.agents.analytics.services.document_fetcher"
            ".pdfplumber.open"
        ) as mock_pdf:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Annual revenue 1000000"
            mock_pdf.return_value.__enter__ = MagicMock(
                return_value=MagicMock(pages=[mock_page])
            )
            mock_pdf.return_value.__exit__ = MagicMock(return_value=False)

            result = await fetch_document("https://example.com/report.pdf")

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_fetch_document_raises_on_http_error() -> None:
    """fetch_document raises DocumentFetchError on a 4xx or 5xx response."""
    with patch(
        "latam_investment_research_agent.agents.analytics.services.document_fetcher"
        ".httpx.AsyncClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            return_value=_make_http_response(404, b"Not found", "text/plain")
        )

        with pytest.raises(DocumentFetchError):
            await fetch_document("https://example.com/missing.pdf")


@pytest.mark.asyncio
async def test_fetch_document_extracts_html_tables() -> None:
    """fetch_document returns extracted table text for an HTML page."""
    html_content = b"""
    <html><body>
    <table>
      <tr><th>Year</th><th>Revenue</th></tr>
      <tr><td>2023</td><td>1000000</td></tr>
    </table>
    </body></html>
    """

    with patch(
        "latam_investment_research_agent.agents.analytics.services.document_fetcher"
        ".httpx.AsyncClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            return_value=_make_http_response(200, html_content, "text/html")
        )

        result = await fetch_document("https://example.com/stats")

    assert "Year" in result or "2023" in result or "Revenue" in result


@pytest.mark.asyncio
async def test_fetch_document_raises_for_non_200_html() -> None:
    """fetch_document raises DocumentFetchError for a non-200 HTML response."""
    with patch(
        "latam_investment_research_agent.agents.analytics.services.document_fetcher"
        ".httpx.AsyncClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            return_value=_make_http_response(404, b"Not found", "text/html")
        )

        with pytest.raises(DocumentFetchError):
            await fetch_document("https://example.com/missing-page")
