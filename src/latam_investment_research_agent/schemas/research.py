"""Research pipeline request/response models (shared by API and services)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.analytics.models.domain import (
    DatasetIngestionFailure,
    DatasetIngestionResult,
)
from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal
from latam_investment_research_agent.agents.retrieval.schemas.routing import RetrievalOutcome

EXAMPLE_SEED_URLS: list[str] = [
    "https://www.infomoney.com.br/business/cooxupe-se-prepara-para-receber-7-milhoes-de-sacas-de-cafe-em-2024/",
    "https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf",
    "https://www.cooxupe.com.br/relatorios-de-gestao-e-demonstracoes-financeiras/",
]

EXAMPLE_QUERIES: list[str] = [
    (
        "Find underfollowed Brazilian agriculture infrastructure opportunities "
        "benefiting from export growth."
    ),
    "Identify underfollowed Brazilian companies benefiting from soybean export growth",
]


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=8)
    seed_urls: list[str] = Field(default_factory=list)
    max_documents: int = Field(default=8, ge=1, le=20)


class ResearchResponse(BaseModel):
    task_id: str
    query: str
    documents: list[NimbleDocument]
    signals: list[MarketSignal]
    retrieval: RetrievalOutcome
    errors: list[str] = Field(default_factory=list)


class ExampleSeedsResponse(BaseModel):
    queries: list[str]
    seed_urls: list[str]


class IngestionSummaryResponse(BaseModel):
    """Per-document outcome from the analytics ingestion graph."""

    source_reference: str
    total_datasets_found: int
    datasets_succeeded: list[DatasetIngestionResult]
    datasets_failed: list[DatasetIngestionFailure]


class SensoIngestionResultResponse(BaseModel):
    """Per-document outcome from Senso KB ingestion."""

    source_reference: str
    ticker: str
    filing_type: str
    fiscal_year: int
    title: str
    kb_node_id: str | None = None
    processing_status: str | None = None
    error: str | None = None


class ResearchWithIngestionResponse(BaseModel):
    """Research pipeline output plus parallel ClickHouse and Senso ingestion."""

    research: ResearchResponse
    ingestion_summaries: list[IngestionSummaryResponse] = Field(default_factory=list)
    senso_ingestion_results: list[SensoIngestionResultResponse] = Field(
        default_factory=list
    )


ReportJobStatusLiteral = Literal["pending", "running", "completed", "failed"]


class ReportJobCreateResponse(BaseModel):
    """Response when a report generation job is accepted."""

    job_id: str
    status: ReportJobStatusLiteral
    query: str


class ReportJobStatusResponse(BaseModel):
    """Pollable status for an analyst report job."""

    job_id: str
    status: ReportJobStatusLiteral
    query: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    documents_ingested: int = 0
    clickhouse_rows: int = 0
    senso_chunks: int = 0
