"""Documents returned by Nimble search, extract, and crawl."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NimbleDocument(BaseModel):
    """
    Raw document from Nimble (HTML, PDF, wiki, image, etc.).

    `raw_body` holds the primary payload for Senso ingest (HTML, markdown,
    or base64-encoded binary). `text` is the extracted plain text used by
    the relevance filter heuristics.
    """

    url: str
    final_url: str
    title: str
    text: str = ""

    content_type: str = "text/html"
    raw_body: str | None = None
    raw_encoding: str = "utf-8"  # utf-8 | base64

    source_type: str = "news"
    fetched_at: datetime
    discovery_source: str = "search"  # search | seed_url | extract

    nimble_task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip() or self.raw_body)
