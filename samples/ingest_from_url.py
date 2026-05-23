"""Sample script: ingest a URL (PDF or webpage) into the Senso KB.

Uses ingest_from_url — auto-detects PDF vs HTML, extracts full page text,
and ingests into the right company folder in Senso.

Usage:
    uv run python samples/ingest_from_url.py
    uv run python samples/ingest_from_url.py <url> <ticker> <filing_type> <fiscal_year>

Examples:
    # Ingest Cooxupé sustainability report (PDF)
    uv run python samples/ingest_from_url.py \\
        https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf \\
        COOXUPE SR 2024

    # Ingest a news article (webpage)
    uv run python samples/ingest_from_url.py \\
        https://www.infomoney.com.br/business/cooxupe-se-prepara-para-receber-7-milhoes-de-sacas-de-cafe-em-2024/ \\
        COOXUPE NEWS 2024

Requires SENSO_API_KEY in your .env file.
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

from latam_investment_research_agent.agents.semantic_storage import (  # noqa: E402
    FilingMetadata,
    ingest_from_url,
)

DEFAULT_URL = (
    "https://www.cooxupe.com.br/wp-content/uploads/2026/04/"
    "ENG_relatorio-web_revisado_completo_compressed.pdf"
)
DEFAULT_TICKER = "COOXUPE"
DEFAULT_FILING_TYPE = "SR"
DEFAULT_FISCAL_YEAR = 2024


async def main(url: str, ticker: str, filing_type: str, fiscal_year: int) -> None:
    print(f"URL:         {url}")
    print(f"Ticker:      {ticker}")
    print(f"Filing type: {filing_type}")
    print(f"Fiscal year: {fiscal_year}\n")

    metadata = FilingMetadata(
        ticker=ticker,
        filing_type=filing_type,
        fiscal_year=fiscal_year,
        source_url=url,
    )

    print("Fetching and extracting text…")
    result = await ingest_from_url(url=url, metadata=metadata)

    print(f"\n✓ Ingested into Senso KB")
    print(f"  Title:      {metadata.document_title()}")
    print(f"  Node ID:    {result.get('kb_node_id') or result.get('content_id', 'ok')}")
    print(f"  Status:     {result.get('content', {}).get('processing_status', 'submitted')}")


if __name__ == "__main__":
    args = sys.argv[1:]
    url = args[0] if len(args) > 0 else DEFAULT_URL
    ticker = args[1] if len(args) > 1 else DEFAULT_TICKER
    filing_type = args[2] if len(args) > 2 else DEFAULT_FILING_TYPE
    fiscal_year = int(args[3]) if len(args) > 3 else DEFAULT_FISCAL_YEAR

    asyncio.run(main(url, ticker, filing_type, fiscal_year))
