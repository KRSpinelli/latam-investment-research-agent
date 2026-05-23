"""Decide ClickHouse / Senso / analysis routing per MarketSignal."""

from latam_investment_research_agent.agents.retrieval.config import (
    RetrievalSettings,
    get_retrieval_settings,
)
from latam_investment_research_agent.agents.retrieval.schemas.enums import (
    SENSO_PREFERRED_SOURCE_TYPES,
)
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal
from latam_investment_research_agent.agents.retrieval.schemas.routing import RouteDecision


def _has_structured_facts(signal: MarketSignal) -> bool:
    return bool(
        signal.companies
        or signal.tickers
        or signal.extracted_metrics
        or signal.commodities
    )


def _should_store_senso(signal: MarketSignal) -> bool:
    if signal.store_senso:
        return True
    if signal.raw_content_body:
        return True
    source = signal.source_type.lower().strip()
    if source in SENSO_PREFERRED_SOURCE_TYPES:
        return True
    if signal.full_text and len(signal.full_text) > 500:
        return True
    return signal.relevance_score >= 0.70 and bool(signal.evidence_snippets)


def _should_store_clickhouse(signal: MarketSignal) -> bool:
    if signal.store_clickhouse:
        return True
    return _has_structured_facts(signal) and signal.relevance_score >= 0.50


def _should_send_to_analysis(signal: MarketSignal, settings: RetrievalSettings) -> bool:
    if signal.send_to_analysis:
        return True
    return (
        signal.relevance_score >= settings.relevance_min_for_analysis
        and signal.confidence >= settings.confidence_min_for_analysis
    )


def route_signal(
    signal: MarketSignal,
    settings: RetrievalSettings | None = None,
) -> RouteDecision:
    """
    Apply routing rules from the pipeline schema.

    Upstream may set store_* flags; this layer enforces thresholds and discard.
    """
    settings = settings or get_retrieval_settings()

    if signal.relevance_score < settings.relevance_discard_below:
        return RouteDecision(
            signal_id=signal.signal_id,
            to_clickhouse=False,
            to_senso=False,
            to_analysis_agent=False,
            discard=True,
            discard_reason=f"relevance_score below {settings.relevance_discard_below}",
        )

    to_clickhouse = _should_store_clickhouse(signal)
    to_senso = _should_store_senso(signal)
    to_analysis = _should_send_to_analysis(signal, settings)

    if not (to_clickhouse or to_senso or to_analysis):
        return RouteDecision(
            signal_id=signal.signal_id,
            to_clickhouse=False,
            to_senso=False,
            to_analysis_agent=False,
            discard=True,
            discard_reason="no store target matched routing rules",
        )

    return RouteDecision(
        signal_id=signal.signal_id,
        to_clickhouse=to_clickhouse,
        to_senso=to_senso,
        to_analysis_agent=to_analysis,
    )


def rank_for_analysis(signals: list[MarketSignal]) -> list[MarketSignal]:
    """Rank by relevance, confidence, then metric density."""

    def score(s: MarketSignal) -> tuple[float, float, int]:
        return (s.relevance_score, s.confidence, len(s.extracted_metrics))

    return sorted(signals, key=score, reverse=True)
