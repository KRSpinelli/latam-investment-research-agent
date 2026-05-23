"""State schemas for the ingestion LangGraph.

Defines the TypedDicts used as graph state plus the public input and output
types exposed to the parent orchestrator.
"""

from __future__ import annotations

from typing import TypedDict

from latam_investment_research_agent.agents.analytics.models.domain import (
    DatasetIngestionFailure,
    DatasetIngestionResult,
    ExtractedDataset,
)


class IngestionState(TypedDict, total=False):
    """Mutable state passed between nodes of the ingestion LangGraph.

    Fields are populated incrementally as the graph executes.  All fields are
    optional (``total=False``) because nodes return only the keys they set.

    Attributes:
        source_reference: URL or absolute file path of the source document.
        raw_content: Raw text extracted from the document (pages joined).
            ``None`` if the fetch node failed.
        extracted_datasets: All datasets identified by the extraction node.
        ingestion_results: Successful write results from ``persist_datasets_node``.
        ingestion_failures: Accumulates failed write details.
        ingestion_summary: Final compiled summary populated by the terminal node.
        error: Set by any node that encounters a fatal error halting the graph.
    """

    source_reference: str
    raw_content: str | None
    extracted_datasets: list[ExtractedDataset]
    ingestion_results: list[DatasetIngestionResult]
    ingestion_failures: list[DatasetIngestionFailure]
    ingestion_summary: IngestionSummary
    error: str | None


class IngestionGraphInput(TypedDict):
    """Public input supplied by the parent orchestrator to the ingestion graph.

    Attributes:
        source_reference: URL (PDF or static web page) or absolute local file path
            to the document to ingest.
    """

    source_reference: str


class IngestionSummary(TypedDict):
    """Structured output returned by the ingestion graph upon completion.

    Attributes:
        source_reference: The source document that was processed.
        total_datasets_found: Number of numerical datasets identified.
        datasets_succeeded: Datasets successfully written to ClickHouse.
        datasets_failed: Datasets that could not be written.
    """

    source_reference: str
    total_datasets_found: int
    datasets_succeeded: list[DatasetIngestionResult]
    datasets_failed: list[DatasetIngestionFailure]
