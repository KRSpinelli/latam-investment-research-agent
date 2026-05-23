"""HTTP client for Nimble search and extract APIs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from latam_investment_research_agent.agents.nimble.config import NimbleSettings
from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument

logger = logging.getLogger(__name__)

_BINARY_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".doc", ".docx", ".xlsx"}


def _infer_content_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return "application/pdf"
    if path.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".gif"):
        return "image/gif"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith((".doc", ".docx")):
        return "application/msword"
    if path.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/html"


def _infer_source_type(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    if "pdf" in content_type.lower() or path.endswith(".pdf"):
        return "company_report"
    if any(token in path for token in ("relatorio", "demonstrac", "filing", "ri/", "investor")):
        return "company_reports"
    if "infomoney" in url.lower():
        return "news"
    return "news"


class NimbleClient:
    """Thin wrapper around Nimble REST API."""

    def __init__(self, settings: NimbleSettings) -> None:
        self._settings = settings

    @property
    def settings(self) -> NimbleSettings:
        return self._settings

    def _require_api_key(self) -> None:
        if not self._settings.api_key:
            msg = "NIMBLE_API_KEY is not set. Add it to .env in the project root."
            raise ValueError(msg)

    def _headers(self) -> dict[str, str]:
        self._require_api_key()
        return {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }

    def _http_timeout(self, *, for_search: bool = False) -> httpx.Timeout:
        read = (
            self._settings.search_timeout_seconds
            if for_search
            else self._settings.timeout_seconds
        )
        return httpx.Timeout(connect=15.0, read=read, write=30.0, pool=15.0)

    def search(
        self,
        query: str,
        *,
        max_results: int = 8,
    ) -> list[NimbleDocument]:
        payload = {
            "query": query,
            "focus": self._settings.search_focus,
            "max_results": max_results,
            "country": self._settings.country,
            "locale": self._settings.locale,
            "search_depth": self._settings.search_depth,
            "output_format": self._settings.output_format,
        }
        url = f"{self._settings.base_url}/search"
        try:
            with httpx.Client(timeout=self._http_timeout(for_search=True)) as client:
                response = client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(
                "Nimble search timed out after %ss (depth=%s). "
                "Try NIMBLE_SEARCH_DEPTH=fast or raise NIMBLE_SEARCH_TIMEOUT_SECONDS.",
                self._settings.search_timeout_seconds,
                self._settings.search_depth,
            )
            return [
                NimbleDocument(
                    url="",
                    final_url="",
                    title="",
                    fetched_at=datetime.now(tz=UTC),
                    error=f"Nimble search timed out: {exc}",
                    discovery_source="search",
                )
            ]
        except Exception as exc:
            logger.exception("Nimble search failed")
            return [
                NimbleDocument(
                    url="",
                    final_url="",
                    title="",
                    fetched_at=datetime.now(tz=UTC),
                    error=str(exc),
                    discovery_source="search",
                )
            ]

        now = datetime.now(tz=UTC)
        documents: list[NimbleDocument] = []
        for row in data.get("results", []):
            doc_url = row.get("url", "")
            content = row.get("content") or row.get("description") or ""
            extra = row.get("extra_fields") or row.get("metadata") or {}
            content_type = _infer_content_type(doc_url)
            documents.append(
                NimbleDocument(
                    url=doc_url,
                    final_url=doc_url,
                    title=row.get("title") or doc_url,
                    text=content,
                    content_type=content_type,
                    raw_body=content or None,
                    raw_encoding="utf-8",
                    source_type=_infer_source_type(doc_url, content_type),
                    fetched_at=now,
                    discovery_source="search",
                    metadata=extra if isinstance(extra, dict) else {},
                )
            )
        return documents

    def extract_url(self, url: str, *, discovery_source: str = "extract") -> NimbleDocument:
        """Fetch a single URL via Nimble /v1/extract (HTML, PDF, images, etc.)."""
        now = datetime.now(tz=UTC)
        path = urlparse(url).path.lower()
        is_binary = any(path.endswith(ext) for ext in _BINARY_EXTENSIONS)
        formats: list[str] = ["html", "markdown"] if not is_binary else ["html"]

        payload: dict[str, Any] = {
            "url": url,
            "render": True,
            "country": self._settings.country,
            "locale": self._settings.locale,
            "formats": formats,
        }
        api_url = f"{self._settings.base_url}/extract"
        try:
            with httpx.Client(timeout=self._http_timeout()) as client:
                response = client.post(api_url, json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("Nimble extract failed for %s: %s", url, exc)
            return NimbleDocument(
                url=url,
                final_url=url,
                title=url,
                fetched_at=now,
                discovery_source=discovery_source,
                error=str(exc),
            )

        content_type = _infer_content_type(str(data.get("url") or url))
        extract_data = data.get("data") or {}
        html = extract_data.get("html") or ""
        markdown = extract_data.get("markdown") or ""
        screenshot = extract_data.get("screenshot")

        raw_encoding = "utf-8"
        if screenshot:
            raw_body = screenshot
            raw_encoding = "base64"
            content_type = "image/png"
            text = ""
        elif markdown:
            raw_body = markdown
            text = markdown
        elif html:
            raw_body = html
            text = html[:50_000]
        else:
            raw_body = None
            text = ""

        final_url = str(data.get("url") or url)
        return NimbleDocument(
            url=url,
            final_url=final_url,
            title=urlparse(final_url).path.split("/")[-1] or final_url,
            text=text.strip(),
            content_type=content_type,
            raw_body=raw_body or None,
            raw_encoding=raw_encoding,
            source_type=_infer_source_type(final_url, content_type),
            fetched_at=now,
            discovery_source=discovery_source,
            nimble_task_id=data.get("task_id"),
            metadata=data.get("metadata") or {},
        )
