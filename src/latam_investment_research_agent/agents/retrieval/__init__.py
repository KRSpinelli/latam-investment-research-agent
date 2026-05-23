"""Retrieval layer: route classified signals to ClickHouse and Senso."""

from latam_investment_research_agent.agents.retrieval.agent import RetrievalAgent
from latam_investment_research_agent.agents.retrieval.schemas.routing import RetrievalOutcome

__all__ = ["RetrievalAgent", "RetrievalOutcome"]
