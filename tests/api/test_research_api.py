from datetime import UTC, datetime

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
