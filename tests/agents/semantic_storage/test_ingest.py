"""Tests for Senso ingest folder routing."""

from __future__ import annotations

from latam_investment_research_agent.agents.semantic_storage.ingest import (
    FilingMetadata,
    _resolve_folder_id,
)
from latam_investment_research_agent.agents.semantic_storage.kb_scaffold import (
    GENERAL_FOLDER_KEY,
)


def test_resolve_folder_id_uses_company_folder_when_registered() -> None:
    folder_map = {"RAIL3": "company-folder", GENERAL_FOLDER_KEY: "general-folder"}

    folder_id = _resolve_folder_id(folder_map, "RAIL3")

    assert folder_id == "company-folder"


def test_resolve_folder_id_falls_back_to_general_folder() -> None:
    folder_map = {"COOXUPE": "company-folder", GENERAL_FOLDER_KEY: "general-folder"}

    folder_id = _resolve_folder_id(folder_map, "")

    assert folder_id == "general-folder"


def test_resolve_folder_id_uses_general_for_unknown_ticker() -> None:
    folder_map = {"COOXUPE": "company-folder", GENERAL_FOLDER_KEY: "general-folder"}

    folder_id = _resolve_folder_id(folder_map, "UNKNOWN4")

    assert folder_id == "general-folder"


def test_document_title_without_ticker() -> None:
    metadata = FilingMetadata(
        ticker="",
        filing_type="NEWS",
        fiscal_year=2024,
    )

    assert metadata.document_title() == "Market research — News Article 2024"


def test_document_title_includes_url_slug_for_uniqueness() -> None:
    metadata = FilingMetadata(
        ticker="",
        filing_type="NEWS",
        fiscal_year=2024,
        source_url="https://datamarnews.com/noticias/brazil-coffee-exports/",
    )

    assert metadata.document_title() == (
        "Market research — News Article 2024 — "
        "datamarnews.com/brazil-coffee-exports"
    )
