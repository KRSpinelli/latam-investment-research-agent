"""LLM-based numerical data extraction service.

Sends document text to an LLM in page-sized batches and collects the
structured ``ExtractedDataset`` responses.  Handles validation errors with
retry logic and uses locale-aware instructions to correctly parse numbers
formatted with period or comma as the decimal separator.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from latam_investment_research_agent.agents.analytics.constants import (
    MAX_CHARS_PER_BATCH,
    MAX_EXTRACTION_RETRIES,
    PAGE_BATCH_SIZE,
    PAGE_SEPARATOR,
)
from latam_investment_research_agent.agents.analytics.models.domain import ExtractedDataset

logger = logging.getLogger(__name__)

_TRUNCATION_NOTICE = (
    "\n\n[NOTE: Text truncated to fit model context limit. "
    "Extract all numerical data visible above.]"
)

_EXTRACTION_SYSTEM_PROMPT = """You are a financial data analyst specialising in Latin American
agricultural commodity reports.  Your task is to extract all numerical datasets from the provided
document text.

IMPORTANT RULES:
1. Extract EVERY table or group of numbers that represents financial or statistical data.
2. Locale-aware number parsing: In Portuguese-language documents, commas are used as decimal
   separators and periods as thousand separators (e.g., "1.234,56" means 1234.56).  Normalise
   all numbers to use a period as the decimal separator.
3. For monetary amounts, represent values as plain decimal strings (e.g., "1234.56"), NOT as
   floats with floating-point imprecision.
4. Infer meaningful column names from table headers or surrounding context.  Use snake_case.
5. If no numerical data is found in the text, return an empty datasets list.
6. Include context_labels with any surrounding captions, table titles, or section headers."""


class _ExtractionResponse(BaseModel):
    """Structured response schema for the LLM extraction call.

    Attributes:
        datasets: List of extracted numerical datasets from the document batch.
    """

    datasets: list[ExtractedDataset]


async def _extract_batch_with_retry(
    batch_text: str,
    structured_llm: Any,
    batch_number: int,
) -> list[ExtractedDataset]:
    """Extract datasets from one page batch, retrying on validation errors.

    Args:
        batch_text: The concatenated text of one page batch.
        structured_llm: An LLM already configured with structured output targeting
            ``_ExtractionResponse``.
        batch_number: Zero-based batch index, used in log messages.

    Returns:
        A list of ``ExtractedDataset`` objects extracted from this batch.
        Returns an empty list if all retries are exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_EXTRACTION_RETRIES + 1):
        prompt = _EXTRACTION_SYSTEM_PROMPT
        if last_error is not None:
            prompt += f"\n\nPrevious attempt failed with: {last_error}\nPlease correct the output."

        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": batch_text},
            ]
            response: _ExtractionResponse = await structured_llm.ainvoke(messages)
            logger.debug(
                "Batch %d extracted %d datasets on attempt %d",
                batch_number,
                len(response.datasets),
                attempt,
            )
            return response.datasets
        except Exception as exc:
            logger.warning(
                "Batch %d extraction attempt %d/%d failed: %s",
                batch_number,
                attempt,
                MAX_EXTRACTION_RETRIES,
                exc,
            )
            last_error = exc

    logger.error(
        "Batch %d failed after %d attempts; skipping.", batch_number, MAX_EXTRACTION_RETRIES
    )
    return []


async def extract_datasets(
    raw_text: str,
    llm: BaseChatModel,
) -> list[ExtractedDataset]:
    """Extract all numerical datasets from document text using an LLM.

    Splits the text into batches of ``PAGE_BATCH_SIZE`` pages (separated by
    ``--- PAGE BREAK ---`` markers), sends each batch to the LLM with a
    structured Pydantic response schema, and retries up to
    ``MAX_EXTRACTION_RETRIES`` times on validation failure.

    Args:
        raw_text: The full text extracted from the source document.  Pages
            should be separated by ``--- PAGE BREAK ---`` markers.
        llm: A ``BaseChatModel`` instance, received via dependency injection.
            Must support ``with_structured_output``.

    Returns:
        A flat list of all ``ExtractedDataset`` objects found across all batches.
        Returns an empty list if ``raw_text`` is empty or no numerical data exists.

    Example:
        datasets = await extract_datasets(document_text, llm_provider)
        for dataset in datasets:
            print(dataset.dataset_name, len(dataset.rows), "rows")
    """
    if not raw_text or not raw_text.strip():
        return []

    pages = raw_text.split(PAGE_SEPARATOR)
    # method="function_calling" avoids OpenAI structured-output's strict JSON Schema
    # requirement that rejects dict[str, Any] fields (additionalProperties must be false).
    structured_llm = llm.with_structured_output(_ExtractionResponse, method="function_calling")

    batch_count = (len(pages) + PAGE_BATCH_SIZE - 1) // PAGE_BATCH_SIZE
    logger.info(
        "Starting extraction: %d page(s) → %d batch(es) of up to %d pages each (all concurrent)",
        len(pages),
        batch_count,
        PAGE_BATCH_SIZE,
    )

    tasks: list[asyncio.Task[list[ExtractedDataset]]] = []
    for batch_index in range(batch_count):
        start_index = batch_index * PAGE_BATCH_SIZE
        end_index = start_index + PAGE_BATCH_SIZE
        batch_pages = pages[start_index:end_index]
        batch_text = PAGE_SEPARATOR.join(batch_pages)
        batch_chars = len(batch_text)

        logger.info(
            "Batch %d/%d queued: pages %d–%d, %d chars",
            batch_index + 1,
            batch_count,
            start_index + 1,
            min(end_index, len(pages)),
            batch_chars,
        )

        if batch_chars > MAX_CHARS_PER_BATCH:
            logger.warning(
                "Batch %d/%d exceeds %d char limit (%d chars) — truncating",
                batch_index + 1,
                batch_count,
                MAX_CHARS_PER_BATCH,
                batch_chars,
            )
            batch_text = batch_text[:MAX_CHARS_PER_BATCH] + _TRUNCATION_NOTICE

        tasks.append(
            asyncio.create_task(
                _extract_batch_with_retry(batch_text, structured_llm, batch_index)
            )
        )

    batch_results: list[list[ExtractedDataset]] = await asyncio.gather(*tasks)

    all_datasets: list[ExtractedDataset] = []
    for batch_index, batch_datasets in enumerate(batch_results):
        logger.info(
            "Batch %d/%d: %d dataset(s) found",
            batch_index + 1,
            batch_count,
            len(batch_datasets),
        )
        all_datasets.extend(batch_datasets)

    logger.info(
        "Extraction complete: %d total dataset(s) across %d batch(es)",
        len(all_datasets),
        batch_count,
    )
    return all_datasets
