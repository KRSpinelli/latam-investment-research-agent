"""
One-time setup: creates the latam-alpha/sector/ticker folder tree in Senso KB.

Returns a FolderMap (dict[ticker, folder_node_id]) that ingest.py uses to
place documents in the right folder.

Run via:
    uv run python -m latam_investment_research_agent.agents.semantic_storage.kb_scaffold
"""

from __future__ import annotations

import asyncio
import json

from .client import SensoClient
from .companies import BY_SECTOR, ROOT_FOLDER_NAME, SECTORS, Company


FolderMap = dict[str, str]  # ticker -> kb_node_id


async def scaffold_kb(client: SensoClient | None = None) -> FolderMap:
    """
    Idempotent: finds existing folders before creating. Returns FolderMap.
    """
    c = client or SensoClient()
    folder_map: FolderMap = {}

    root = await c.kb_root()
    root_id: str = root["kb_node_id"]

    latam = await c.kb_find_or_create_folder(ROOT_FOLDER_NAME, parent_id=root_id)
    latam_id: str = latam["kb_node_id"]
    print(f"  ✓ {ROOT_FOLDER_NAME}  [{latam_id}]")

    for sector in SECTORS:
        companies: list[Company] = BY_SECTOR[sector]
        sector_node = await c.kb_find_or_create_folder(sector, parent_id=latam_id)
        sector_id: str = sector_node["kb_node_id"]
        print(f"    ✓ {sector}  [{sector_id}]")

        for company in companies:
            folder_name = f"{company.ticker}-{company.name.replace(' ', '')}"
            company_node = await c.kb_find_or_create_folder(folder_name, parent_id=sector_id)
            company_id: str = company_node["kb_node_id"]
            folder_map[company.ticker] = company_id
            print(f"      ✓ {folder_name}  [{company_id}]")

    return folder_map


async def _main() -> None:
    folder_map = await scaffold_kb()
    print("\nFolder map (save this for ingest):")
    print(json.dumps(folder_map, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
