from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    sector: str
    cvm_code: str | None = None


# Target universe for LatAm Alpha — Brazilian public equities
COMPANIES: list[Company] = [
    # Logistics
    Company(ticker="RAIL3", name="Rumo", sector="logistics", cvm_code="20532"),
    Company(ticker="HVTL3", name="Hidrovias do Brasil", sector="logistics", cvm_code="23264"),
    Company(ticker="STBP3", name="Santos Brasil", sector="logistics", cvm_code="18376"),
    # Agriculture
    Company(ticker="SLCE3", name="SLC Agricola", sector="agriculture", cvm_code="16179"),
    Company(ticker="AGRO3", name="BrasilAgro", sector="agriculture", cvm_code="19909"),
    # Energy
    Company(ticker="ENEV3", name="Eneva", sector="energy", cvm_code="22020"),
    Company(ticker="CPFE3", name="CPFL Energia", sector="energy", cvm_code="18539"),
]

SECTORS: list[str] = sorted({c.sector for c in COMPANIES})

BY_TICKER: dict[str, Company] = {c.ticker: c for c in COMPANIES}
BY_SECTOR: dict[str, list[Company]] = {
    sector: [c for c in COMPANIES if c.sector == sector] for sector in SECTORS
}


def kb_path(company: Company) -> str:
    """Returns the canonical KB folder path for a company."""
    return f"latam-alpha/{company.sector}/{company.ticker}-{company.name.replace(' ', '')}"
