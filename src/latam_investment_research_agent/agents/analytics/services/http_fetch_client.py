"""Shared HTTP client settings for public document fetching."""

from __future__ import annotations

import logging
import os
import ssl

import certifi
import httpx

logger = logging.getLogger(__name__)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_DEFAULT_HEADERS = {
    "User-Agent": _BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def document_fetch_verify_setting() -> ssl.SSLContext | bool:
    """Return TLS verification settings for outbound document HTTP requests.

    Uses the certifi CA bundle (fixes common macOS Python SSL issues). Set
    ``DOCUMENT_FETCH_VERIFY_TLS=false`` to disable verification for debugging only.

    Returns:
        SSL context with certifi CAs, or ``False`` when verification is disabled.
    """
    raw_value = os.getenv("DOCUMENT_FETCH_VERIFY_TLS", "true").strip().lower()
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return ssl.create_default_context(cafile=certifi.where())


def build_document_fetch_client(*, verify: ssl.SSLContext | bool | None = None) -> httpx.AsyncClient:
    """Build an HTTP client for fetching PDF/HTML research documents.

    Args:
        verify: TLS verification override; defaults to :func:`document_fetch_verify_setting`.

    Returns:
        Configured async HTTP client (use as a context manager).
    """
    if verify is None:
        verify = document_fetch_verify_setting()
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
        verify=verify,
        headers=_DEFAULT_HEADERS,
    )


def _is_ssl_certificate_error(error: httpx.RequestError) -> bool:
    """Return True when the request failed due to TLS certificate verification."""
    return "CERTIFICATE_VERIFY_FAILED" in str(error)


async def fetch_http_document(url: str) -> httpx.Response:
    """GET a document URL with browser-like headers and TLS verification.

    On macOS/Python installs with incomplete CA bundles, retries once without TLS
    verification when the first attempt fails with ``CERTIFICATE_VERIFY_FAILED``.

    Args:
        url: HTTP or HTTPS document URL.

    Returns:
        Successful HTTP response (caller should check content type).

    Raises:
        httpx.HTTPStatusError: On non-success HTTP status after retries.
        httpx.RequestError: On network failures that cannot be recovered.
    """
    async with build_document_fetch_client() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
        except httpx.RequestError as error:
            verify = document_fetch_verify_setting()
            if not _is_ssl_certificate_error(error) or verify is False:
                raise
            logger.warning(
                "TLS verify failed for %s; retrying once without certificate verification",
                url,
            )

    async with build_document_fetch_client(verify=False) as fallback_client:
        response = await fallback_client.get(url)
        response.raise_for_status()
        return response
