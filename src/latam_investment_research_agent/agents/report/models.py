"""Data models for the analyst report pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryOutput
from latam_investment_research_agent.agents.semantic_storage.search import Chunk
from latam_investment_research_agent.schemas.research import ResearchWithIngestionResponse


class ReportNarrative(BaseModel):
    """Structured narrative sections produced by the report LLM."""

    executive_summary: str = Field(description="High-level summary for portfolio managers.")
    key_findings: list[str] = Field(
        default_factory=list,
        description="Bullet points of the most important takeaways.",
    )
    quantitative_analysis: str = Field(
        description="Interpretation of ClickHouse / RAG query results."
    )
    qualitative_analysis: str = Field(
        description="Interpretation of Senso semantic search excerpts."
    )
    limitations: str = Field(
        description="Data gaps, ingestion failures, and caveats."
    )
    methodology: str = Field(
        description="How sources were gathered, ingested, and queried."
    )


@dataclass
class ChartArtifact:
    """A matplotlib chart written to disk for PDF embedding."""

    title: str
    file_path: Path
    chart_type: str


@dataclass
class ReportContext:
    """All artifacts needed to render the final analyst PDF."""

    query: str
    job_directory: Path
    ingestion: ResearchWithIngestionResponse
    rag_output: RAGQueryOutput
    query_result_records: list[dict[str, Any]] = field(default_factory=list)
    senso_chunks: list[Chunk] = field(default_factory=list)
    narrative: ReportNarrative | None = None
    charts: list[ChartArtifact] = field(default_factory=list)
