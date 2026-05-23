"""Sample script: research web sources, then ingest numerical data into ClickHouse.

Usage:
    uv run python samples/research_and_ingest_numeric.py
    uv run python samples/research_and_ingest_numeric.py "What were total export revenues by year?"

Requires a configured .env file at the project root (copy from .env.sample).
"""

import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from latam_investment_research_agent.api.deps import get_pipeline  # noqa: E402
from latam_investment_research_agent.schemas.research import (  # noqa: E402
    EXAMPLE_QUERIES,
    ResearchRequest,
    ResearchWithIngestionResponse,
)
from latam_investment_research_agent.services.research_and_ingest import (  # noqa: E402
    run_research_and_ingest,
)

DEFAULT_QUERY = EXAMPLE_QUERIES[1]


def _print_research_summary(result: ResearchWithIngestionResponse) -> None:
    research = result.research
    print(f"Task ID:     {research.task_id}")
    print(f"Query:       {research.query}")
    print(f"Documents:   {len(research.documents)}")
    print(f"Signals:     {len(research.signals)}")
    print(
        f"Retrieval:   {research.retrieval.signals_processed} signal(s) processed, "
        f"analysis packet {research.retrieval.analysis_packet_id!r}"
    )

    if research.errors:
        print("\nResearch errors:")
        for error in research.errors:
            print(f"  ✗ {error}")

    if research.documents:
        print("\nDocuments:")
        for document in research.documents:
            status = "ok" if document.ok else "failed"
            print(f"  [{status}] {document.final_url or document.url}")


def _print_ingestion_summaries(result: ResearchWithIngestionResponse) -> None:
    if not result.ingestion_summaries:
        print("\nNo documents were ingested into ClickHouse.")
        return

    print(f"\nIngested {len(result.ingestion_summaries)} document(s) into ClickHouse:\n")
    for summary in result.ingestion_summaries:
        print(f"Source: {summary.source_reference}")
        print(f"  Datasets found:  {summary.total_datasets_found}")
        print(f"  Succeeded:       {len(summary.datasets_succeeded)}")
        print(f"  Failed:          {len(summary.datasets_failed)}")

        if summary.datasets_succeeded:
            print("  Succeeded:")
            for dataset_result in summary.datasets_succeeded:
                print(
                    f"    → {dataset_result.dataset_name}  →  "
                    f"table '{dataset_result.target_table_name}'  "
                    f"({dataset_result.rows_written} rows written)"
                )

        if summary.datasets_failed:
            print("  Failed:")
            for dataset_failure in summary.datasets_failed:
                print(f"    ✗ {dataset_failure.dataset_name}: {dataset_failure.error_detail}")

        print()


async def main(query: str) -> None:
    print(f"Research query: {query}\n")

    request = ResearchRequest(query=query)
    pipeline = get_pipeline()
    result = await run_research_and_ingest(request, pipeline)

    print("--- Research ---\n")
    _print_research_summary(result)
    print("\n--- Numeric ingestion ---")
    _print_ingestion_summaries(result)


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    asyncio.run(main(query))
