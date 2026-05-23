"""Retrieval agent: route MarketSignals to ClickHouse, Senso, and analysis packet."""

import uuid

from latam_investment_research_agent.agents.retrieval.clickhouse_client import (
    ClickHouseWriter,
    InMemoryClickHouseWriter,
)
from latam_investment_research_agent.agents.retrieval.config import (
    RetrievalSettings,
    get_retrieval_settings,
)
from latam_investment_research_agent.agents.retrieval.mappers import (
    to_clickhouse_metric_rows,
    to_clickhouse_signal_row,
    to_senso_document,
)
from latam_investment_research_agent.agents.retrieval.router import rank_for_analysis, route_signal
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal
from latam_investment_research_agent.agents.retrieval.schemas.routing import RetrievalOutcome
from latam_investment_research_agent.agents.retrieval.senso_client import (
    InMemorySensoWriter,
    SensoWriter,
)


class RetrievalAgent:
    """
    Consumes classified MarketSignals from the relevance filter.

    Writes structured rows to ClickHouse, semantic documents to Senso, and
    returns top signals for the analysis agent.
    """

    def __init__(
        self,
        *,
        clickhouse: ClickHouseWriter | None = None,
        senso: SensoWriter | None = None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        self._clickhouse = clickhouse or InMemoryClickHouseWriter()
        self._senso = senso or InMemorySensoWriter()
        self._settings = settings or get_retrieval_settings()

    def ingest(self, signals: list[MarketSignal]) -> RetrievalOutcome:
        decisions = [route_signal(s, self._settings) for s in signals]

        signal_rows = []
        metric_rows = []
        senso_docs = []
        analysis_candidates: list[MarketSignal] = []
        discarded = 0

        for signal, decision in zip(signals, decisions, strict=True):
            if decision.discard:
                discarded += 1
                continue
            if decision.to_clickhouse:
                signal_rows.append(to_clickhouse_signal_row(signal))
                metric_rows.extend(to_clickhouse_metric_rows(signal))
            if decision.to_senso:
                senso_docs.append(to_senso_document(signal))
            if decision.to_analysis_agent:
                analysis_candidates.append(signal)

        ch_signals = self._clickhouse.insert_signal_rows(signal_rows)
        ch_metrics = self._clickhouse.insert_metric_rows(metric_rows)
        senso_count = self._senso.ingest_documents(senso_docs)

        ranked = rank_for_analysis(analysis_candidates)
        top = ranked[: self._settings.max_analysis_signals]
        packet_id = f"packet_{uuid.uuid4().hex[:12]}" if top else None

        return RetrievalOutcome(
            signals_processed=len(signals),
            signals_discarded=discarded,
            clickhouse_signal_rows_inserted=ch_signals,
            clickhouse_metric_rows_inserted=ch_metrics,
            senso_documents_inserted=senso_count,
            analysis_packet_id=packet_id,
            analysis_signals=top,
            route_decisions=decisions,
        )
