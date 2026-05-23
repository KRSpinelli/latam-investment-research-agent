from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument
from latam_investment_research_agent.agents.relevance.agent import RelevanceFilterAgent
from latam_investment_research_agent.agents.retrieval.agent import RetrievalAgent
from latam_investment_research_agent.agents.retrieval.clickhouse_client import (
    InMemoryClickHouseWriter,
)
from latam_investment_research_agent.agents.retrieval.senso_client import InMemorySensoWriter
from latam_investment_research_agent.api.app import create_app
from latam_investment_research_agent.api.deps import get_pipeline
from latam_investment_research_agent.services.research_pipeline import ResearchPipeline


class _FakeNimble:
    def acquire(
        self,
        query: str,
        *,
        max_results: int = 8,
        seed_urls: list[str] | None = None,
    ) -> list[NimbleDocument]:
        del query, max_results
        urls = seed_urls or ["https://example.com/soybean-exports"]
        now = datetime(2026, 5, 23, 14, 0, tzinfo=UTC)
        return [
            NimbleDocument(
                url=url,
                final_url=url,
                title="Brazil soybean exports rise at major ports",
                text=(
                    "Brazilian soybean export growth accelerated at major ports in the south. "
                    "Ticker RAIL3 linked to logistics and rail capacity expansion. "
                    "Soybeans shipped to China increased year over year. "
                    "Analysts note underfollowed infrastructure names "
                    "may benefit from export growth. "
                    "Port congestion remains a bottleneck for agricultural shipments. "
                    "Companies tied to soybean export corridors include "
                    "logistics and storage operators."
                ),
                raw_body="<html><body>Brazilian soybean export growth accelerated.</body></html>",
                content_type="text/html",
                source_type="news",
                fetched_at=now,
                discovery_source="seed_url",
            )
            for url in urls
        ]


def _test_client() -> TestClient:
    pipeline = ResearchPipeline(
        nimble=_FakeNimble(),
        relevance=RelevanceFilterAgent(),
        retrieval=RetrievalAgent(
            clickhouse=InMemoryClickHouseWriter(),
            senso=InMemorySensoWriter(),
        ),
    )
    app = create_app()
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    return TestClient(app)


def test_health() -> None:
    client = _test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_research_examples() -> None:
    client = _test_client()
    response = client.get("/api/v1/research/examples")
    assert response.status_code == 200
    body = response.json()
    assert len(body["queries"]) >= 1
    assert "cooxupe" in body["seed_urls"][0]


def test_run_research_pipeline() -> None:
    client = _test_client()
    response = client.post(
        "/api/v1/research",
        json={
            "query": (
                "Identify underfollowed Brazilian companies "
                "benefiting from soybean export growth"
            ),
            "seed_urls": ["https://example.com/soybean-exports"],
            "max_documents": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"].startswith("task_")
    assert len(body["documents"]) >= 1
    assert len(body["signals"]) >= 1
    assert body["retrieval"]["signals_processed"] >= 1
    assert body["retrieval"]["analysis_packet_id"] is not None


def test_run_research_and_ingest_parallel() -> None:
    client = _test_client()
    mock_summary = {
        "source_reference": "https://example.com/soybean-exports",
        "total_datasets_found": 1,
        "datasets_succeeded": [],
        "datasets_failed": [],
    }
    mock_senso = {
        "source_reference": "https://example.com/soybean-exports",
        "ticker": "RAIL3",
        "filing_type": "NEWS",
        "fiscal_year": 2024,
        "title": "RAIL3 — News Article 2024",
        "kb_node_id": "node_123",
        "processing_status": "submitted",
        "error": None,
    }
    with (
        patch(
            "latam_investment_research_agent.services.research_and_ingest._ingest_clickhouse_source_safe",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ) as mock_clickhouse_ingest,
        patch(
            "latam_investment_research_agent.services.research_and_ingest.ingest_sources_to_senso",
            new_callable=AsyncMock,
            return_value=[mock_senso],
        ) as mock_senso_ingest,
    ):
        response = client.post(
            "/api/v1/research/ingest",
            json={
                "query": (
                    "Identify underfollowed Brazilian companies "
                    "benefiting from soybean export growth"
                ),
                "seed_urls": ["https://example.com/soybean-exports"],
                "max_documents": 3,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["research"]["task_id"].startswith("task_")
    assert len(body["research"]["documents"]) >= 1
    assert len(body["ingestion_summaries"]) == 1
    assert body["ingestion_summaries"][0]["source_reference"] == mock_summary["source_reference"]
    assert len(body["senso_ingestion_results"]) == 1
    assert body["senso_ingestion_results"][0]["kb_node_id"] == "node_123"
    mock_clickhouse_ingest.assert_awaited_once()
    mock_senso_ingest.assert_awaited_once()
