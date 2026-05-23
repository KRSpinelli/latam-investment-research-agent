"""Unit tests for the numerical data extraction service.

Uses a mock BaseChatModel — no live LLM calls.
Run and confirm FAILING before implementing services/numerical_extractor.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.constants import (
    MAX_EXTRACTION_RETRIES,
    PAGE_BATCH_SIZE,
)
from latam_investment_research_agent.agents.analytics.models.domain import ExtractedDataset
from latam_investment_research_agent.agents.analytics.services.numerical_extractor import (
    extract_datasets,
)


def _make_extracted_dataset_response(dataset_name: str = "Test Dataset") -> MagicMock:
    """Build a mock structured LLM response containing one ExtractedDataset.

    Args:
        dataset_name: Name to use for the dataset in the mock response.

    Returns:
        A MagicMock simulating a structured LLM output.
    """
    mock_response = MagicMock()
    mock_response.datasets = [
        ExtractedDataset(
            dataset_name=dataset_name,
            context_labels=["Annual Report 2023"],
            column_names=["year", "revenue_brl"],
            rows=[{"year": 2023, "revenue_brl": "1000000.00"}],
        )
    ]
    return mock_response


@pytest.mark.asyncio
async def test_extract_datasets_returns_list_of_extracted_datasets(
    mock_llm_provider: MagicMock,
) -> None:
    """extract_datasets returns a list of ExtractedDataset objects."""
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=_make_extracted_dataset_response()
    )

    raw_text = "Page 1 content with financial tables..."
    result = await extract_datasets(raw_text, mock_llm_provider)

    assert isinstance(result, list)
    assert all(isinstance(dataset, ExtractedDataset) for dataset in result)


@pytest.mark.asyncio
async def test_extract_datasets_sends_pages_in_batches(
    mock_llm_provider: MagicMock,
) -> None:
    """extract_datasets sends text in batches of PAGE_BATCH_SIZE pages."""
    mock_llm_provider.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=_make_extracted_dataset_response()
    )

    page_separator = "\n--- PAGE BREAK ---\n"
    total_pages = PAGE_BATCH_SIZE + 2
    raw_text = page_separator.join(f"Page {i} content" for i in range(total_pages))

    await extract_datasets(raw_text, mock_llm_provider)

    expected_batch_count = (total_pages + PAGE_BATCH_SIZE - 1) // PAGE_BATCH_SIZE
    actual_call_count = mock_llm_provider.with_structured_output.return_value.ainvoke.call_count
    assert actual_call_count == expected_batch_count


@pytest.mark.asyncio
async def test_extract_datasets_returns_empty_list_for_empty_text(
    mock_llm_provider: MagicMock,
) -> None:
    """extract_datasets returns an empty list when raw_text is empty."""
    result = await extract_datasets("", mock_llm_provider)
    assert result == []
    mock_llm_provider.with_structured_output.return_value.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_extract_datasets_retries_on_validation_error(
    mock_llm_provider: MagicMock,
) -> None:
    """extract_datasets retries up to MAX_EXTRACTION_RETRIES on validation failure."""

    call_count = 0

    async def flaky_invoke(*args: object, **kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < MAX_EXTRACTION_RETRIES:
            raise ValueError("Schema validation failed")
        return _make_extracted_dataset_response()

    mock_llm_provider.with_structured_output.return_value.ainvoke = flaky_invoke

    result = await extract_datasets("Some financial content", mock_llm_provider)
    assert call_count == MAX_EXTRACTION_RETRIES
    assert isinstance(result, list)
