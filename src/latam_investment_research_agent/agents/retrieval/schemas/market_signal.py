"""Unified signal from the relevance filter (upstream input to retrieval)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.retrieval.schemas.enums import (
    Impact,
    Sentiment,
    SignalType,
    TimeHorizon,
)


class ExtractedMetricPayload(BaseModel):
    """Metric embedded on MarketSignal before expansion to ClickHouse rows."""

    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    metric_period: str | None = Field(default=None, alias="period")
    related_entity: str | None = None
    related_ticker: str | None = None
    sector: str | None = None
    direction: str | None = None
    evidence_sentence: str | None = None
    confidence: float | None = None

    model_config = {"populate_by_name": True}


class MarketSignal(BaseModel):
    """
    Classified signal produced by Nimble acquisition + relevance filter.

    Retrieval emits ClickHouse rows (structured fields), Senso JSON payloads
    (raw documents), and an analysis packet id.
    """

    signal_id: str
    task_id: str
    document_id: str

    title: str
    url: str
    source: str
    source_type: str
    published_at: datetime | None = None
    crawled_at: datetime

    country: str = "Brazil"
    sector: str
    subsector: str | None = None

    companies: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    commodities: list[str] = Field(default_factory=list)

    signal_type: SignalType = "other"
    impact: Impact = "unclear"
    sentiment: Sentiment = "neutral"
    time_horizon: TimeHorizon = "unclear"

    summary: str
    evidence_snippets: list[str] = Field(default_factory=list)
    extracted_metrics: list[ExtractedMetricPayload] = Field(default_factory=list)

    relevance_score: float
    confidence: float

    full_text: str | None = None
    full_text_ref: str | None = None

    # Raw document from Nimble — forwarded to Senso as JSON
    raw_content_type: str | None = None
    raw_content_body: str | None = None
    raw_content_encoding: str = "utf-8"
    nimble_task_id: str | None = None
    nimble_metadata: dict[str, Any] = Field(default_factory=dict)

    store_clickhouse: bool = False
    store_senso: bool = False
    send_to_analysis: bool = False
