from datetime import UTC, datetime

from latam_investment_research_agent.agents.retrieval.config import RetrievalSettings
from latam_investment_research_agent.agents.retrieval.router import route_signal
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import (
    ExtractedMetricPayload,
    MarketSignal,
)


def _signal(**overrides: object) -> MarketSignal:
    base = {
        "signal_id": "sig_1",
        "task_id": "task_1",
        "document_id": "doc_1",
        "title": "Brazil soybean exports rise",
        "url": "https://example.com/article",
        "source": "Reuters",
        "source_type": "news",
        "crawled_at": datetime(2026, 5, 23, 14, 0, tzinfo=UTC),
        "sector": "Agriculture",
        "summary": "Exports accelerated.",
        "relevance_score": 0.91,
        "confidence": 0.86,
        "companies": ["Rumo"],
        "tickers": ["RAIL3"],
        "evidence_snippets": ["Exports rose 18% YoY."],
        "extracted_metrics": [
            ExtractedMetricPayload(
                metric_name="soybean_export_growth",
                metric_value=18.4,
                metric_unit="percent",
            )
        ],
    }
    base.update(overrides)
    return MarketSignal(**base)  # type: ignore[arg-type]


def test_discards_low_relevance() -> None:
    decision = route_signal(
        _signal(relevance_score=0.3),
        settings=RetrievalSettings(),
    )
    assert decision.discard is True
    assert decision.discard_reason is not None


def test_routes_high_quality_signal_to_all_targets() -> None:
    decision = route_signal(_signal(), settings=RetrievalSettings())
    assert decision.discard is False
    assert decision.to_clickhouse is True
    assert decision.to_senso is True
    assert decision.to_analysis_agent is True


def test_filing_prefers_senso_even_without_full_text() -> None:
    decision = route_signal(
        _signal(source_type="filings", full_text=None, relevance_score=0.65),
        settings=RetrievalSettings(),
    )
    assert decision.to_senso is True
