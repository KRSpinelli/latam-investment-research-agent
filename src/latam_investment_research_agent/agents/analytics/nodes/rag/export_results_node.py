"""RAG graph node: export query results to a timestamped CSV file via Polars.

Converts the merged query result records to a Polars DataFrame and writes
a CSV file with a deterministic, human-readable filename.

CSV naming convention:
    {YYYYMMDD_HHMMSS}_{question_slug}.csv
where ``question_slug`` is the first 40 characters of the question,
lowercased, with non-alphanumeric characters replaced by underscores.

See: contracts/rag_query_graph.md § CSV File Naming
     research.md § CSV Export
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars

from latam_investment_research_agent.agents.analytics.constants import MANDATORY_AUDIT_COLUMNS
from latam_investment_research_agent.agents.analytics.models.rag_state import RAGQueryState

logger = logging.getLogger(__name__)

_SOURCE_REFERENCE_COLUMN = MANDATORY_AUDIT_COLUMNS[0]

_SLUG_MAX_LENGTH = 40
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^a-z0-9]+")


def _build_question_slug(question: str) -> str:
    """Convert the natural-language question to a safe filename slug.

    Args:
        question: The raw natural-language question string.

    Returns:
        A lowercase alphanumeric slug of at most 40 characters.
    """
    lowercased = question.lower()
    slugified = _NON_ALPHANUMERIC_PATTERN.sub("_", lowercased)
    stripped = slugified.strip("_")
    return stripped[:_SLUG_MAX_LENGTH]


def _generate_export_filename(question: str) -> str:
    """Generate a timestamped CSV filename for the export.

    Args:
        question: The raw natural-language question used to derive the slug.

    Returns:
        A filename string of the form ``YYYYMMDD_HHMMSS_{slug}.csv``.
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    slug = _build_question_slug(question)
    return f"{timestamp}_{slug}.csv"


def _prepare_export_dataframe(records: list[dict[str, Any]]) -> polars.DataFrame:
    """Build a Polars DataFrame for CSV export with ``source_reference`` first.

    Args:
        records: Merged query result rows.

    Returns:
        A DataFrame guaranteed to include a ``source_reference`` column.
    """
    normalized_records: list[dict[str, Any]] = []
    for record in records:
        export_row = dict(record)
        if _SOURCE_REFERENCE_COLUMN not in export_row:
            export_row[_SOURCE_REFERENCE_COLUMN] = None
        normalized_records.append(export_row)

    dataframe = polars.from_dicts(normalized_records)
    other_columns = [
        column_name
        for column_name in dataframe.columns
        if column_name != _SOURCE_REFERENCE_COLUMN
    ]
    return dataframe.select([_SOURCE_REFERENCE_COLUMN, *other_columns])


async def export_results_node(state: RAGQueryState) -> dict[str, Any]:
    """Write query result records to a CSV file using Polars.

    When ``state["query_result_records"]`` is empty, returns
    ``{"export_file_path": None}`` without creating a file.

    The export directory is created if it does not already exist.

    Args:
        state: The current RAG query graph state.

    Returns:
        A dict with ``export_file_path`` (str | None).
    """
    records: list[dict[str, Any]] = state.get("query_result_records", [])
    question: str = state["natural_language_question"]
    export_directory: str = state.get("export_directory", "./exports")

    if not records:
        logger.info("No result records to export — skipping CSV write.")
        return {"export_file_path": None}

    export_path = Path(export_directory)
    export_path.mkdir(parents=True, exist_ok=True)

    filename = _generate_export_filename(question)
    absolute_file_path = export_path / filename

    dataframe = _prepare_export_dataframe(records)
    dataframe.write_csv(str(absolute_file_path))

    logger.info(
        "Exported %d row(s) to %s",
        len(records),
        absolute_file_path,
    )
    return {"export_file_path": str(absolute_file_path)}
