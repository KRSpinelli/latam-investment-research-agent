"""Tests for Senso ingestion helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from latam_investment_research_agent.agents.retrieval.schemas.market_signal import (
    MarketSignal,
)
from latam_investment_research_agent.agents.retrieval.schemas.routing import (
    RetrievalOutcome,
)
from latam_investment_research_agent.schemas.research import ResearchResponse
from latam_investment_research_agent.services.semantic_storage_ingestion import (
    build_filing_metadata,
)


def _research_with_signal(url: str, *, tickers: list[str]) -> ResearchResponse:
    signal = MarketSignal(
        signal_id="sig_test",
        task_id="task_test",
        document_id="doc_test",
        title="Test document",
        url=url,
        source="example.com",
        source_type="news",
        crawled_at=datetime(2024, 5, 1, tzinfo=UTC),
        sector="Agriculture",
        summary="Soybean exports",
        tickers=tickers,
        relevance_score=0.8,
        confidence=0.7,
    )
    return ResearchResponse(
        task_id="task_test",
        query="soybean exports Brazil",
        documents=[],
        signals=[signal],
        retrieval=RetrievalOutcome(
            signals_processed=1,
            signals_discarded=0,
            analysis_packet_id=None,
        ),
    )


def test_build_filing_metadata_uses_signal_ticker() -> None:
    url = "https://example.com/soybean-exports"
    metadata = build_filing_metadata(url, _research_with_signal(url, tickers=["RAIL3"]))

    assert metadata.ticker == "RAIL3"
    assert metadata.filing_type == "NEWS"
    assert metadata.fiscal_year == 2024


def test_build_filing_metadata_without_ticker_uses_empty_ticker() -> None:
    url = "https://www.stonex.com/en-gb/insights/brazil-coffee-exports/"
    research = ResearchResponse(
        task_id="task_test",
        query="coffee export revenues",
        documents=[],
        signals=[],
        retrieval=RetrievalOutcome(
            signals_processed=0,
            signals_discarded=0,
            analysis_packet_id=None,
        ),
    )

    metadata = build_filing_metadata(url, research)

    assert metadata.ticker == ""
    assert metadata.filing_type == "NEWS"
    assert "Market research" in metadata.document_title()


def test_build_filing_metadata_maps_cooxupe_host() -> None:
    url = "https://www.cooxupe.com.br/report.pdf"
    research = ResearchResponse(
        task_id="task_test",
        query="coffee cooperative",
        documents=[],
        signals=[],
        retrieval=RetrievalOutcome(
            signals_processed=0,
            signals_discarded=0,
            analysis_packet_id=None,
        ),
    )

    metadata = build_filing_metadata(url, research)

    assert metadata.ticker == "COOXUPE"
    assert metadata.filing_type == "SR"
