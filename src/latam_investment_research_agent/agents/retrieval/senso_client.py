"""Senso.ai writer interface (implement with Senso SDK / HTTP in integration step)."""

from typing import Protocol

from latam_investment_research_agent.agents.retrieval.schemas.senso import SensoDocumentPayload


class SensoWriter(Protocol):
    def ingest_documents(self, documents: list[SensoDocumentPayload]) -> int: ...


class InMemorySensoWriter:
    """Stub for local dev and tests."""

    def __init__(self) -> None:
        self.documents: list[SensoDocumentPayload] = []

    def ingest_documents(self, documents: list[SensoDocumentPayload]) -> int:
        self.documents.extend(documents)
        return len(documents)
