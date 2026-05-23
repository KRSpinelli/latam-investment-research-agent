"""Shared HTTP client settings for public document fetching."""

from __future__ import annotations

import os
import ssl

import certifi
import httpx

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


def build_document_fetch_client() -> httpx.AsyncClient:
    """Build an HTTP client for fetching PDF/HTML research documents.

    Returns:
        Configured async HTTP client (use as a context manager).
    """
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
        verify=document_fetch_verify_setting(),
        headers=_DEFAULT_HEADERS,
    )
