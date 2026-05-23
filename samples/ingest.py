"""Sample script: ingest a financial PDF into ClickHouse.

Usage:
    uv run python samples/ingest.py
    uv run python samples/ingest.py https://example.com/report.pdf

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

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig  # noqa: E402
from latam_investment_research_agent.agents.analytics.graph.ingestion_graph import (  # noqa: E402
    build_ingestion_graph,
)
from latam_investment_research_agent.agents.analytics.providers.clickhouse_provider import (  # noqa: E402
    create_clickhouse_client,
)

DEFAULT_SOURCE = (
    "https://www.cooxupe.com.br/wp-content/uploads/2026/04/"
    "ENG_relatorio-web_revisado_completo_compressed.pdf"
)


async def main(source_reference: str) -> None:
    print(f"Ingesting: {source_reference}\n")

    config = AnalyticsConfig()
    clickhouse_client = await create_clickhouse_client(config)
    graph = build_ingestion_graph(config=config, clickhouse_client=clickhouse_client)

    result = await graph.ainvoke({"source_reference": source_reference})
    summary = result["ingestion_summary"]

    print(f"\nDatasets found:  {summary['total_datasets_found']}")
    print(f"Succeeded:       {len(summary['datasets_succeeded'])}")
    print(f"Failed:          {len(summary['datasets_failed'])}")

    if summary["datasets_succeeded"]:
        print("\nSucceeded:")
        for r in summary["datasets_succeeded"]:
            print(f"  → {r.dataset_name}  →  table '{r.target_table_name}'  ({r.rows_written} rows written)")

    if summary["datasets_failed"]:
        print("\nFailed:")
        for f in summary["datasets_failed"]:
            print(f"  ✗ {f.dataset_name}: {f.error_detail}")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    asyncio.run(main(source))
