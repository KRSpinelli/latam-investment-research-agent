from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    ticker: str       # B3 ticker or internal identifier for non-listed entities
    name: str
    sector: str
    cvm_code: str | None = None   # CVM code (None for cooperatives / non-listed)
    listed: bool = True           # False for cooperatives / private companies


COMPANIES: list[Company] = [
    # Logistics
    Company(ticker="RAIL3", name="Rumo", sector="logistics", cvm_code="20532"),
    Company(ticker="HVTL3", name="Hidrovias do Brasil", sector="logistics", cvm_code="23264"),
    Company(ticker="STBP3", name="Santos Brasil", sector="logistics", cvm_code="18376"),
    # Agriculture
    Company(ticker="SLCE3", name="SLC Agricola", sector="agriculture", cvm_code="16179"),
    Company(ticker="AGRO3", name="BrasilAgro", sector="agriculture", cvm_code="19909"),
    # Energy
    Company(ticker="ENEV3", name="Eneva", sector="energy", cvm_code="20532"),
    Company(ticker="CPFE3", name="CPFL Energia", sector="energy", cvm_code="18539"),
    # Coffee (demo — cooperative, not listed on B3)
    Company(ticker="COOXUPE", name="Cooxupe", sector="coffee", cvm_code=None, listed=False),
]

SECTORS: list[str] = sorted({c.sector for c in COMPANIES})

BY_TICKER: dict[str, Company] = {c.ticker: c for c in COMPANIES}
BY_SECTOR: dict[str, list[Company]] = {
    sector: [c for c in COMPANIES if c.sector == sector] for sector in SECTORS
}

ROOT_FOLDER_NAME = "latam-alpha"
