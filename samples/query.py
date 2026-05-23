"""Sample script: query ingested data with a natural-language question.

Usage:
    uv run python samples/query.py
    uv run python samples/query.py "What were total export revenues by year?"

Requires a configured .env file at the project root (copy from .env.sample).
Results are exported to ./exports/ as a timestamped CSV.
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
from latam_investment_research_agent.agents.analytics.graph.rag_query_graph import (  # noqa: E402
    build_rag_query_graph,
)
from latam_investment_research_agent.agents.analytics.providers.clickhouse_provider import (  # noqa: E402
    managed_clickhouse_client,
)

DEFAULT_QUESTION = "What were total export revenues by year?"


async def main(question: str) -> None:
    print(f"Question: {question}\n")

    config = AnalyticsConfig()
    async with managed_clickhouse_client(config) as clickhouse_client:
        graph = build_rag_query_graph(config=config, clickhouse_client=clickhouse_client)
        result = await graph.ainvoke({
            "natural_language_question": question,
            "export_row_limit": 10000,
            "export_directory": "./exports",
        })

    out = result["rag_query_output"]

    if out["export_file_path"] is None:
        print(f"No data found.\nRationale: {out['rationale']}")
        return

    print(f"\nCSV exported to: {out['export_file_path']}")
    print(f"Rows:            {out['row_count']}  (truncated: {out['was_truncated']})")
    print(f"\nRationale:\n{out['rationale']}")
    print("\nSQL used:")
    for sql in out["sql_queries_used"]:
        print(f"  {sql}")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    asyncio.run(main(question))
