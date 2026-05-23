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


class ReportPdfLayoutHints(BaseModel):
    """Layout adjustments applied when re-rendering the PDF after review."""

    page_break_before_charts: bool = Field(
        default=True,
        description="Start charts on a new page.",
    )
    page_break_before_data_snapshot: bool = Field(
        default=True,
        description="Start the data table on a new page.",
    )
    page_break_before_appendix: bool = Field(
        default=True,
        description="Start limitations/methodology/SQL on a new page.",
    )
    chart_display_order: list[str] = Field(
        default_factory=lambda: ["line", "bar", "pie"],
        description="Order to display charts (line, bar, pie).",
    )
    max_sql_queries_in_appendix: int = Field(
        default=8,
        ge=1,
        le=30,
        description="Maximum SQL queries listed in the appendix.",
    )


class ReportFormattingReview(BaseModel):
    """Output from the PDF formatting review agent."""

    narrative: ReportNarrative = Field(
        description="Copy-edited narrative with improved flow and consistency.",
    )
    layout_hints: ReportPdfLayoutHints = Field(
        default_factory=ReportPdfLayoutHints,
        description="Structural layout fixes for the final PDF render.",
    )
    formatting_changes_summary: str = Field(
        default="",
        description="Brief note on what was cleaned up (for logs).",
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
    layout_hints: ReportPdfLayoutHints | None = None
