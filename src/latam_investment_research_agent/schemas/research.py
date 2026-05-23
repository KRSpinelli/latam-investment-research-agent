"""Research pipeline request/response models (shared by API and services)."""

from pydantic import BaseModel, Field

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
