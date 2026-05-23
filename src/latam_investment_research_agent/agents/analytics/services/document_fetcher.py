"""Document fetching service for the ingestion agent.

Supports two source types:
- **PDF documents**: fetched via HTTP or read from a local file path, then
  parsed with ``pdfplumber`` to extract text from all pages.
- **HTML pages**: fetched via HTTP and parsed with ``BeautifulSoup`` to extract
  text from all ``<table>`` elements.

Source type is determined from the URL content-type header or file extension.
"""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from latam_investment_research_agent.agents.analytics.constants import PAGE_SEPARATOR

logger = logging.getLogger(__name__)


class DocumentFetchError(Exception):
    """Raised when a document cannot be fetched or parsed.

    Attributes:
        source_reference: The URL or file path that could not be fetched.
        message: Human-readable description of the failure.
    """

    def __init__(self, source_reference: str, message: str) -> None:
        """Initialise a DocumentFetchError.

        Args:
            source_reference: The URL or file path that failed.
            message: Description of the failure reason.
        """
        super().__init__(f"Failed to fetch '{source_reference}': {message}")
        self.source_reference = source_reference
        self.message = message


def _is_pdf_content_type(content_type: str) -> bool:
    """Return True if the Content-Type header indicates a PDF document.

    Args:
        content_type: The value of the HTTP Content-Type response header.

    Returns:
        True if the content type is ``application/pdf``.
    """
    return "application/pdf" in content_type.lower()


def _extract_text_from_pdf_bytes(pdf_bytes: bytes, source_reference: str) -> str:
    """Extract all text from a PDF given as raw bytes.

    Iterates over all pages and joins their text with newlines.

    Args:
        pdf_bytes: Raw bytes of the PDF document.
        source_reference: The URL or path of the document (used in error messages).

    Returns:
        All extracted text joined with newlines.

    Raises:
        DocumentFetchError: If ``pdfplumber`` cannot open or parse the bytes.
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf_document:
            total_pages = len(pdf_document.pages)
            logger.info("Parsing PDF: %d pages found in '%s'", total_pages, source_reference)
            page_texts: list[str] = []
            for page_index, page in enumerate(pdf_document.pages):
                page_text = page.extract_text()
                if page_text:
                    page_texts.append(page_text)
                else:
                    logger.debug("Page %d/%d yielded no text (image-only?)", page_index + 1, total_pages)
            non_empty = len(page_texts)
            logger.info(
                "PDF extraction complete: %d/%d pages had text, ~%d chars total",
                non_empty,
                total_pages,
                sum(len(t) for t in page_texts),
            )
            return PAGE_SEPARATOR.join(page_texts)
    except Exception as exc:
        raise DocumentFetchError(source_reference, f"PDF parsing failed: {exc}") from exc


def _extract_text_from_html_bytes(html_bytes: bytes) -> str:
    """Extract text from all HTML table elements in the given bytes.

    Uses ``BeautifulSoup`` with the built-in ``html.parser`` to find all
    ``<table>`` elements and render each row as tab-separated values.

    Args:
        html_bytes: Raw bytes of the HTML page.

    Returns:
        Extracted table content as plain text, tables separated by blank lines.
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    all_tables = soup.find_all("table")
    logger.info("HTML parsing: found %d <table> element(s)", len(all_tables))
    table_texts: list[str] = []

    for table_index, table in enumerate(all_tables):
        rows: list[str] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            row_text = "\t".join(cell.get_text(strip=True) for cell in cells)
            if row_text.strip():
                rows.append(row_text)
        if rows:
            logger.debug("Table %d: %d rows extracted", table_index + 1, len(rows))
            table_texts.append("\n".join(rows))
        else:
            logger.debug("Table %d: no text rows found, skipping", table_index + 1)

    logger.info("HTML extraction complete: %d non-empty table(s), ~%d chars", len(table_texts), sum(len(t) for t in table_texts))
    return "\n\n".join(table_texts)


async def fetch_document(source_reference: str) -> str:
    """Fetch a document from a URL or local file path and return its text content.

    Determines the source type from the HTTP Content-Type header (for URLs) or
    the file extension (for local paths).  PDF documents are parsed with
    ``pdfplumber``; HTML pages have their table content extracted with
    ``BeautifulSoup``.

    Args:
        source_reference: A URL pointing to a PDF or static HTML page, or an
            absolute local file path to a PDF document.

    Returns:
        The extracted text content of the document.  For PDFs this is all page
        text joined with newlines.  For HTML pages this is the text of all
        ``<table>`` elements.

    Raises:
        DocumentFetchError: If the document cannot be fetched (HTTP error, network
            failure) or cannot be parsed (corrupt PDF, unsupported format).

    Example:
        text = await fetch_document("https://example.com/annual_report.pdf")
        print(text[:200])
    """
    if not source_reference.startswith(("http://", "https://")):
        return _fetch_local_pdf(source_reference)

    logger.info("Fetching document: %s", source_reference)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as http_client:
        try:
            response = await http_client.get(source_reference)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DocumentFetchError(
                source_reference,
                f"HTTP {exc.response.status_code} response",
            ) from exc
        except httpx.RequestError as exc:
            raise DocumentFetchError(
                source_reference, f"Network error: {exc}"
            ) from exc

        content_type = response.headers.get("content-type", "")
        content_length_kb = len(response.content) / 1024
        url_lower = source_reference.lower()
        logger.info(
            "Response received: %.1f KB, content-type: %s",
            content_length_kb,
            content_type,
        )

        if _is_pdf_content_type(content_type) or url_lower.endswith(".pdf"):
            logger.info("Detected PDF — extracting text via pdfplumber")
            return _extract_text_from_pdf_bytes(response.content, source_reference)

        logger.info("Detected HTML — extracting table text via BeautifulSoup")
        return _extract_text_from_html_bytes(response.content)


def _fetch_local_pdf(file_path: str) -> str:
    """Read and extract text from a local PDF file.

    Args:
        file_path: Absolute path to a local PDF file.

    Returns:
        Extracted text from all pages.

    Raises:
        DocumentFetchError: If the file does not exist or cannot be parsed.
    """
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        return _extract_text_from_pdf_bytes(pdf_bytes, file_path)
    except FileNotFoundError as exc:
        raise DocumentFetchError(file_path, f"File not found: {file_path}") from exc
