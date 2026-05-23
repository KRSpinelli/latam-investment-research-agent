"""FastAPI dependency injection."""

from functools import lru_cache

from latam_investment_research_agent.agents.retrieval.agent import RetrievalAgent
from latam_investment_research_agent.agents.retrieval.clickhouse_client import (
    InMemoryClickHouseWriter,
)
from latam_investment_research_agent.agents.retrieval.senso_client import InMemorySensoWriter
from latam_investment_research_agent.services.research_pipeline import (
    ResearchPipeline,
    get_research_pipeline,
)


@lru_cache
def get_retrieval_agent() -> RetrievalAgent:
    return RetrievalAgent(
        clickhouse=InMemoryClickHouseWriter(),
        senso=InMemorySensoWriter(),
    )


def get_pipeline() -> ResearchPipeline:
    return get_research_pipeline(get_retrieval_agent())
