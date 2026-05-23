"""Run the retrieval agent on sample signals and print what gets stored.

Usage (from repo root):
    uv sync --extra dev
    uv run python scripts/demo_retrieval.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from latam_investment_research_agent.agents.retrieval.agent import RetrievalAgent
from latam_investment_research_agent.agents.retrieval.clickhouse_client import (
    InMemoryClickHouseWriter,
)
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import (
    ExtractedMetricPayload,
    MarketSignal,
)
from latam_investment_research_agent.agents.retrieval.senso_client import InMemorySensoWriter

_CRAWLED = datetime(2026, 5, 23, 14, 0, tzinfo=UTC)


def _sample_signals() -> list[MarketSignal]:
    """Three signals: routed everywhere, Senso filing, and discarded."""
    return [
        MarketSignal(
            signal_id="sig_high",
            task_id="task_demo",
            document_id="doc_high",
            title="Brazil soybean exports rise",
            url="https://example.com/soybeans",
            source="Reuters",
            source_type="news",
            crawled_at=_CRAWLED,
            sector="Agriculture",
            summary="Exports accelerated due to China demand.",
            evidence_snippets=["Exports rose 18% YoY."],
            companies=["Rumo"],
            tickers=["RAIL3"],
            commodities=["Soybeans"],
            signal_type="export_growth",
            impact="bullish",
            sentiment="positive",
            relevance_score=0.91,
            confidence=0.86,
            raw_content_type="text/html",
            raw_content_body="<html><body>Exports rose 18% YoY.</body></html>",
            extracted_metrics=[
                ExtractedMetricPayload(
                    metric_name="soybean_export_growth",
                    metric_value=18.4,
                    metric_unit="percent",
                )
            ],
        ),
        MarketSignal(
            signal_id="sig_filing",
            task_id="task_demo",
            document_id="doc_filing",
            title="Petrobras Q1 operational update",
            url="https://example.com/pbr-filing",
            source="CVM",
            source_type="filings",
            crawled_at=_CRAWLED,
            sector="Energy",
            summary="Production held steady; capex guidance unchanged.",
            companies=["Petrobras"],
            tickers=["PETR4"],
            relevance_score=0.65,
            confidence=0.72,
        ),
        MarketSignal(
            signal_id="sig_noise",
            task_id="task_demo",
            document_id="doc_noise",
            title="Unrelated sports headline",
            url="https://example.com/sports",
            source="Blog",
            source_type="news",
            crawled_at=_CRAWLED,
            sector="Other",
            summary="Local team wins championship.",
            relevance_score=0.25,
            confidence=0.40,
        ),
    ]


def main() -> None:
    clickhouse = InMemoryClickHouseWriter()
    senso = InMemorySensoWriter()
    agent = RetrievalAgent(clickhouse=clickhouse, senso=senso)

    signals = _sample_signals()
    outcome = agent.ingest(signals)

    print("=== Retrieval outcome ===")
    print(outcome.model_dump_json(indent=2))

    print("\n=== ClickHouse signal rows ===")
    print(
        json.dumps(
            [r.model_dump(mode="json") for r in clickhouse.signal_rows],
            indent=2,
            default=str,
        )
    )

    print("\n=== ClickHouse metric rows ===")
    print(
        json.dumps(
            [r.model_dump(mode="json") for r in clickhouse.metric_rows],
            indent=2,
            default=str,
        )
    )

    print("\n=== Senso documents ===")
    print(
        json.dumps(
            [d.model_dump(mode="json") for d in senso.documents],
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
