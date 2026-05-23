"""Nimble API configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NimbleSettings:
    api_key: str
    base_url: str = "https://sdk.nimbleway.com/v1"
    timeout_seconds: float = 180.0
    search_timeout_seconds: float = 180.0
    country: str = "BR"
    locale: str = "pt-BR"
    search_focus: str = "news"
    search_depth: str = "fast"
    output_format: str = "markdown"


def get_nimble_settings() -> NimbleSettings:
    timeout = float(os.getenv("NIMBLE_TIMEOUT_SECONDS", "180"))
    search_timeout = float(os.getenv("NIMBLE_SEARCH_TIMEOUT_SECONDS", str(timeout)))
    return NimbleSettings(
        api_key=os.getenv("NIMBLE_API_KEY", "").strip(),
        base_url=os.getenv("NIMBLE_BASE_URL", "https://sdk.nimbleway.com/v1").rstrip("/"),
        timeout_seconds=timeout,
        search_timeout_seconds=search_timeout,
        country=os.getenv("NIMBLE_COUNTRY", "BR").strip(),
        locale=os.getenv("NIMBLE_LOCALE", "pt-BR").strip(),
        search_focus=os.getenv("NIMBLE_SEARCH_FOCUS", "news").strip(),
        search_depth=os.getenv("NIMBLE_SEARCH_DEPTH", "fast").strip(),
        output_format=os.getenv("NIMBLE_OUTPUT_FORMAT", "markdown").strip(),
    )
