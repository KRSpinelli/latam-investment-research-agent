"""
One-time setup: creates the sector/company folder tree in Senso KB.

Run via:  uv run python -m latam_investment_research_agent.agents.semantic_storage.kb_scaffold
"""

import asyncio

from .client import SensoClient
from .companies import COMPANIES, kb_path


async def scaffold_kb(client: SensoClient | None = None) -> None:
    c = client or SensoClient()

    folders: list[str] = ["latam-alpha"]

    sectors_seen: set[str] = set()
    for company in COMPANIES:
        sector_path = f"latam-alpha/{company.sector}"
        if sector_path not in sectors_seen:
            folders.append(sector_path)
            sectors_seen.add(sector_path)
        folders.append(kb_path(company))

    print(f"Creating {len(folders)} KB folders...")
    for path in folders:
        await c.create_folder(path)
        print(f"  ✓ {path}")

    print("KB scaffold complete.")


if __name__ == "__main__":
    asyncio.run(scaffold_kb())
