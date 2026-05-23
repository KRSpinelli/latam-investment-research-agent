"""Payloads for Senso.ai semantic memory (reports, news, filings)."""

from datetime import datetime

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.retrieval.schemas.enums import SignalType


class SensoChunk(BaseModel):
    """Text chunk with citation metadata for grounded retrieval."""

    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    char_start: int | None = None
    char_end: int | None = None


class SensoDocumentPayload(BaseModel):
    """
    Full document ingest for Senso.

    Includes chunks + metadata used for filtering and citations in the
    analysis agent.
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

    chunks: list[SensoChunk] = Field(default_factory=list)

    # Citation / traceability back to pipeline
    relevance_score: float
    confidence: float
    classification_reasoning: str | None = None
