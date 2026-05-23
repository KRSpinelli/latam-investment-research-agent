"""Orchestrates Nimble acquisition → relevance filter → retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from latam_investment_research_agent.agents.nimble.agent import NimbleAgent, get_nimble_agent
from latam_investment_research_agent.agents.relevance.agent import RelevanceFilterAgent
from latam_investment_research_agent.agents.retrieval.agent import RetrievalAgent
from latam_investment_research_agent.schemas.research import ResearchRequest, ResearchResponse


@dataclass
class ResearchPipeline:
    nimble: NimbleAgent
    relevance: RelevanceFilterAgent
    retrieval: RetrievalAgent

    def run(self, request: ResearchRequest) -> ResearchResponse:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        errors: list[str] = []

        documents = self.nimble.acquire(
            request.query,
            max_results=request.max_documents,
            seed_urls=request.seed_urls,
        )
        ok_docs = [d for d in documents if d.ok]
        if not ok_docs:
            errors.append("No documents returned from Nimble search or seed_urls.")

        failed = [d.url for d in documents if not d.ok]
        if failed:
            errors.append(f"Failed or empty fetch for {len(failed)} URL(s).")

        signals = self.relevance.classify(request.query, ok_docs, task_id=task_id)
        if not signals and ok_docs:
            errors.append("Nimble documents did not produce any MarketSignals.")

        retrieval = self.retrieval.ingest(signals)

        return ResearchResponse(
            task_id=task_id,
            query=request.query,
            documents=documents,
            signals=signals,
            retrieval=retrieval,
            errors=errors,
        )


def get_research_pipeline(retrieval: RetrievalAgent) -> ResearchPipeline:
    return ResearchPipeline(
        nimble=get_nimble_agent(),
        relevance=RelevanceFilterAgent(),
        retrieval=retrieval,
    )
