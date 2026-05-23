"""Sample script: research web sources, then ingest into ClickHouse and Senso.

Runs the same path as ``POST /api/v1/research/ingest``:
  Nimble → relevance → retrieval → parallel ClickHouse + Senso ingestion per URL.

Usage:
    uv run python samples/research_and_ingest.py
    uv run python samples/research_and_ingest.py "Your research question here?"

    # Optional: pass seed URLs after the query
    uv run python samples/research_and_ingest.py \\
        "Coffee export revenues Brazil" \\
        https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf

Requires ``.env`` with at least:
  NIMBLE_API_KEY, OPENAI_API_KEY, CLICKHOUSE_* , SENSO_API_KEY
"""

from __future__ import annotations

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
    EXAMPLE_SEED_URLS,
    ResearchRequest,
    ResearchWithIngestionResponse,
)
from latam_investment_research_agent.services.research_and_ingest import (  # noqa: E402
    run_research_and_ingest,
)

DEFAULT_QUERY = (
    "What were total export revenues by year for coffee exporters in Brazil?"
)


def _print_research_summary(result: ResearchWithIngestionResponse) -> None:
    research = result.research
    print(f"Task ID:     {research.task_id}")
    print(f"Query:       {research.query}")
    print(f"Documents:   {len(research.documents)}")
    print(f"Signals:     {len(research.signals)}")
    print(
        f"Retrieval:   {research.retrieval.signals_processed} signal(s) processed, "
        f"{research.retrieval.signals_discarded} discarded, "
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

    if research.signals:
        print("\nSignals (top tickers per URL):")
        for signal in research.signals:
            tickers = ", ".join(signal.tickers) if signal.tickers else "—"
            print(f"  {signal.url[:72]}{'…' if len(signal.url) > 72 else ''}")
            print(f"    tickers: {tickers}  relevance: {signal.relevance_score:.2f}")


def _print_clickhouse_ingestion(result: ResearchWithIngestionResponse) -> None:
    summaries = result.ingestion_summaries
    if not summaries:
        print("\nNo documents were ingested into ClickHouse.")
        return

    print(f"\nClickHouse — {len(summaries)} document(s):\n")
    for summary in summaries:
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
                    f"({dataset_result.rows_written} rows)"
                )

        if summary.datasets_failed:
            print("  Failed:")
            for dataset_failure in summary.datasets_failed:
                print(f"    ✗ {dataset_failure.dataset_name}: {dataset_failure.error_detail}")

        print()


def _print_senso_ingestion(result: ResearchWithIngestionResponse) -> None:
    senso_results = result.senso_ingestion_results
    if not senso_results:
        print("\nNo documents were ingested into Senso.")
        return

    print(f"\nSenso — {len(senso_results)} document(s):\n")
    for senso_result in senso_results:
        print(f"Source: {senso_result.source_reference}")
        print(f"  Title:       {senso_result.title}")
        print(f"  Ticker:      {senso_result.ticker or 'general (research folder)'}")
        print(f"  Filing type: {senso_result.filing_type or '—'}")
        print(f"  Fiscal year: {senso_result.fiscal_year}")
        if senso_result.error:
            print(f"  ✗ {senso_result.error}")
        else:
            print(f"  Node ID:     {senso_result.kb_node_id}")
            print(f"  Status:      {senso_result.processing_status}")
        print()


def _print_run_summary(result: ResearchWithIngestionResponse) -> None:
    datasets_written = sum(
        len(summary.datasets_succeeded) for summary in result.ingestion_summaries
    )
    senso_ok = sum(1 for item in result.senso_ingestion_results if not item.error)

    print("--- Summary ---")
    if result.ingestion_summaries:
        print(
            f"  ClickHouse: {len(result.ingestion_summaries)} document(s), "
            f"{datasets_written} dataset(s) written"
        )
    else:
        print("  ClickHouse: no URLs ingested")

    if result.senso_ingestion_results:
        print(
            f"  Senso:      {senso_ok}/{len(result.senso_ingestion_results)} "
            "document(s) succeeded"
        )
    else:
        print("  Senso:      no URLs ingested")


def _parse_arguments() -> tuple[str, list[str]]:
    arguments = sys.argv[1:]
    if not arguments:
        return DEFAULT_QUERY, list(EXAMPLE_SEED_URLS)

    query = arguments[0]
    seed_urls = [argument for argument in arguments[1:] if argument.startswith("http")]
    if not seed_urls:
        seed_urls = list(EXAMPLE_SEED_URLS)
    return query, seed_urls


async def main(query: str, seed_urls: list[str]) -> None:
    print(f"Research query: {query}")
    if seed_urls:
        print(f"Seed URLs:      {len(seed_urls)}")
        for seed_url in seed_urls:
            print(f"  • {seed_url}")
    print()

    request = ResearchRequest(query=query, seed_urls=seed_urls)
    pipeline = get_pipeline()
    result = await run_research_and_ingest(request, pipeline)

    print("--- Research ---\n")
    _print_research_summary(result)

    print("\n--- ClickHouse ingestion ---")
    _print_clickhouse_ingestion(result)

    print("--- Senso ingestion ---")
    _print_senso_ingestion(result)

    print()
    _print_run_summary(result)


if __name__ == "__main__":
    parsed_query, parsed_seed_urls = _parse_arguments()
    asyncio.run(main(parsed_query, parsed_seed_urls))
