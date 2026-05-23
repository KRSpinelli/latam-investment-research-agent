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


def test_ingest_writes_to_both_stores() -> None:
    ch = InMemoryClickHouseWriter()
    senso = InMemorySensoWriter()
    agent = RetrievalAgent(clickhouse=ch, senso=senso)

    signal = MarketSignal(
        signal_id="sig_1",
        task_id="task_1",
        document_id="doc_1",
        title="Brazil soybean exports rise",
        url="https://example.com/article",
        source="Reuters",
        source_type="news",
        crawled_at=datetime(2026, 5, 23, 14, 0, tzinfo=UTC),
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
        extracted_metrics=[
            ExtractedMetricPayload(
                metric_name="soybean_export_growth",
                metric_value=18.4,
                metric_unit="percent",
            )
        ],
    )

    outcome = agent.ingest([signal])

    assert outcome.clickhouse_signal_rows_inserted == 1
    assert outcome.clickhouse_metric_rows_inserted == 1
    assert outcome.senso_documents_inserted == 1
    assert outcome.analysis_packet_id is not None
    assert len(outcome.analysis_signals) == 1
