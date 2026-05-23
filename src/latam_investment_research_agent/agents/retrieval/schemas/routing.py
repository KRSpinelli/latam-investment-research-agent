"""Routing decisions and retrieval run outcome."""

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal


class RouteDecision(BaseModel):
    """Per-signal routing from the router node."""

    signal_id: str
    to_clickhouse: bool
    to_senso: bool
    to_analysis_agent: bool
    discard: bool = False
    discard_reason: str | None = None


class RetrievalOutcome(BaseModel):
    """Result of a retrieval agent run (MVP API response shape)."""

    signals_processed: int
    signals_discarded: int

    clickhouse_signal_rows_inserted: int = 0
    clickhouse_metric_rows_inserted: int = 0
    senso_documents_inserted: int = 0

    analysis_packet_id: str | None = None
    analysis_signals: list[MarketSignal] = Field(default_factory=list)

    route_decisions: list[RouteDecision] = Field(default_factory=list)
