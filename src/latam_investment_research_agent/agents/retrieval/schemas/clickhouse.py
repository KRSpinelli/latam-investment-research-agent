"""Rows written to ClickHouse (structured analytics / time-series)."""

from datetime import datetime

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.retrieval.schemas.enums import (
    Impact,
    Sentiment,
    SignalType,
    TimeHorizon,
)


class ClickHouseSignalRow(BaseModel):
    """
    Maps to `market_signals` MergeTree table (see PLAN.md).

    One row per classified signal; queryable by country, sector, time.
    """

    signal_id: str
    document_id: str
    task_id: str

    published_at: datetime | None = None
    crawled_at: datetime

    country: str
    sector: str
    subsector: str | None = None

    source: str
    source_type: str
    url: str

    company: list[str] = Field(default_factory=list)
    ticker: list[str] = Field(default_factory=list)
    commodities: list[str] = Field(default_factory=list)

    signal_type: SignalType
    impact: Impact
    sentiment: Sentiment
    time_horizon: TimeHorizon

    relevance_score: float
    confidence: float
    summary: str


class ClickHouseMetricRow(BaseModel):
    """
    Optional per-metric table for time-series / factor queries.

    Emitted when `extracted_metrics` is non-empty and store_clickhouse is true.
    """

    metric_id: str
    signal_id: str
    document_id: str
    task_id: str

    published_at: datetime | None = None
    crawled_at: datetime

    country: str
    sector: str
    subsector: str | None = None

    source: str
    url: str

    company: list[str] = Field(default_factory=list)
    ticker: list[str] = Field(default_factory=list)
    commodities: list[str] = Field(default_factory=list)

    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    metric_period: str | None = None

    related_entity: str | None = None
    related_ticker: str | None = None

    signal_type: SignalType
    impact: Impact
    sentiment: Sentiment

    relevance_score: float
    confidence: float
    evidence_sentence: str | None = None
