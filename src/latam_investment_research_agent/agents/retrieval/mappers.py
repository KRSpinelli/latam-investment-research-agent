"""Map MarketSignal → ClickHouse rows and Senso ingest payloads."""

import uuid

from latam_investment_research_agent.agents.retrieval.schemas.clickhouse import (
    ClickHouseMetricRow,
    ClickHouseSignalRow,
)
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal
from latam_investment_research_agent.agents.retrieval.schemas.senso import (
    SensoChunk,
    SensoDocumentPayload,
)
from latam_investment_research_agent.agents.retrieval.text_chunks import chunk_text


def to_clickhouse_signal_row(signal: MarketSignal) -> ClickHouseSignalRow:
    return ClickHouseSignalRow(
        signal_id=signal.signal_id,
        document_id=signal.document_id,
        task_id=signal.task_id,
        published_at=signal.published_at,
        crawled_at=signal.crawled_at,
        country=signal.country,
        sector=signal.sector,
        subsector=signal.subsector,
        source=signal.source,
        source_type=signal.source_type,
        url=signal.url,
        company=signal.companies,
        ticker=signal.tickers,
        commodities=signal.commodities,
        signal_type=signal.signal_type,
        impact=signal.impact,
        sentiment=signal.sentiment,
        time_horizon=signal.time_horizon,
        relevance_score=signal.relevance_score,
        confidence=signal.confidence,
        summary=signal.summary,
    )


def to_clickhouse_metric_rows(signal: MarketSignal) -> list[ClickHouseMetricRow]:
    rows: list[ClickHouseMetricRow] = []
    for metric in signal.extracted_metrics:
        rows.append(
            ClickHouseMetricRow(
                metric_id=f"met_{uuid.uuid4().hex[:12]}",
                signal_id=signal.signal_id,
                document_id=signal.document_id,
                task_id=signal.task_id,
                published_at=signal.published_at,
                crawled_at=signal.crawled_at,
                country=signal.country,
                sector=signal.sector,
                subsector=signal.subsector,
                source=signal.source,
                url=signal.url,
                company=signal.companies,
                ticker=signal.tickers,
                commodities=signal.commodities,
                metric_name=metric.metric_name,
                metric_value=metric.metric_value,
                metric_unit=metric.metric_unit,
                metric_period=metric.metric_period,
                related_entity=metric.related_entity,
                related_ticker=metric.related_ticker,
                signal_type=signal.signal_type,
                impact=signal.impact,
                sentiment=signal.sentiment,
                relevance_score=signal.relevance_score,
                confidence=(
                    metric.confidence if metric.confidence is not None else signal.confidence
                ),
                evidence_sentence=metric.evidence_sentence,
            )
        )
    return rows


def to_senso_document(signal: MarketSignal) -> SensoDocumentPayload:
    body = signal.full_text or "\n\n".join(
        [signal.summary, *signal.evidence_snippets]
    ).strip()
    chunks = [
        SensoChunk(
            chunk_id=f"chk_{signal.document_id}_{i}",
            document_id=signal.document_id,
            text=text,
            chunk_index=i,
        )
        for i, text in enumerate(chunk_text(body))
    ]
    return SensoDocumentPayload(
        document_id=signal.document_id,
        signal_id=signal.signal_id,
        task_id=signal.task_id,
        title=signal.title,
        url=signal.url,
        source=signal.source,
        source_type=signal.source_type,
        published_at=signal.published_at,
        crawled_at=signal.crawled_at,
        country=signal.country,
        sector=signal.sector,
        subsector=signal.subsector,
        companies=signal.companies,
        tickers=signal.tickers,
        commodities=signal.commodities,
        signal_type=signal.signal_type,
        summary=signal.summary,
        evidence_snippets=signal.evidence_snippets,
        chunks=chunks,
        relevance_score=signal.relevance_score,
        confidence=signal.confidence,
    )
