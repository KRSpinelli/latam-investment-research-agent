"""Nimble API configuration."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NimbleSettings:
    api_key: str
    base_url: str = "https://sdk.nimbleway.com/v1"
    timeout_seconds: float = 180.0
    search_timeout_seconds: float = 180.0
    country: str = "BR"
    locale: str = "pt-BR"
    search_focus: str = "news"
    search_depth: str = "lite"
    output_format: str = "markdown"


def _resolve_search_depth(search_focus: str, search_depth: str) -> str:
    """Return a Nimble-compatible search depth for the given focus.

    Nimble only allows ``search_depth=fast`` when ``focus=general``. Other focus
    modes (e.g. ``news``) must use ``lite`` or ``deep``.

    Args:
        search_focus: Nimble search focus (``general``, ``news``, etc.).
        search_depth: Requested depth (``lite``, ``fast``, or ``deep``).

    Returns:
        A depth value accepted by the Nimble search API.
    """
    if search_depth == "fast" and search_focus != "general":
        logger.warning(
            "NIMBLE_SEARCH_DEPTH=fast requires NIMBLE_SEARCH_FOCUS=general; "
            "using lite for focus=%r instead.",
            search_focus,
        )
        return "lite"
    return search_depth


def get_nimble_settings() -> NimbleSettings:
    timeout = float(os.getenv("NIMBLE_TIMEOUT_SECONDS", "180"))
    search_timeout = float(os.getenv("NIMBLE_SEARCH_TIMEOUT_SECONDS", str(timeout)))
    search_focus = os.getenv("NIMBLE_SEARCH_FOCUS", "news").strip()
    search_depth = os.getenv("NIMBLE_SEARCH_DEPTH", "lite").strip()
    return NimbleSettings(
        api_key=os.getenv("NIMBLE_API_KEY", "").strip(),
        base_url=os.getenv("NIMBLE_BASE_URL", "https://sdk.nimbleway.com/v1").rstrip("/"),
        timeout_seconds=timeout,
        search_timeout_seconds=search_timeout,
        country=os.getenv("NIMBLE_COUNTRY", "BR").strip(),
        locale=os.getenv("NIMBLE_LOCALE", "pt-BR").strip(),
        search_focus=search_focus,
        search_depth=_resolve_search_depth(search_focus, search_depth),
        output_format=os.getenv("NIMBLE_OUTPUT_FORMAT", "markdown").strip(),
    )
