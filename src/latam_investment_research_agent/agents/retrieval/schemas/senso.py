"""Payloads for Senso.ai semantic memory (raw documents + metadata)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.retrieval.schemas.enums import SignalType


class SensoRawContent(BaseModel):
    """
    Raw document body for Senso ingest (implemented by Senso team).

    Supports HTML, markdown, PDF bytes, images, etc. Binary payloads use
    encoding='base64'.
    """

    content_type: str
    encoding: str = "utf-8"
    body: str


class SensoDocumentPayload(BaseModel):
    """
    JSON document handed off to Senso.ai.

    Includes the raw document plus pipeline metadata for filtering and
    citations in the analysis agent.
    """

    document_id: str
    signal_id: str
    task_id: str

    title: str
    url: str
    canonical_url: str | None = None

    source: str
    source_type: str
    published_at: datetime | None = None
    crawled_at: datetime
    language: str | None = None

    country: str
    sector: str
    subsector: str | None = None

    companies: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    commodities: list[str] = Field(default_factory=list)

    signal_type: SignalType
    summary: str
    evidence_snippets: list[str] = Field(default_factory=list)

    raw_content: SensoRawContent

    nimble_task_id: str | None = None
    nimble_metadata: dict[str, Any] = Field(default_factory=dict)

    relevance_score: float
    confidence: float
    classification_reasoning: str | None = None
