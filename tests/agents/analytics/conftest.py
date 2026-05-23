"""Shared pytest fixtures for analytics agent tests.

Provides mock LLM providers and ClickHouse test client helpers used across
unit and integration test suites.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig


@pytest.fixture
def analytics_config() -> AnalyticsConfig:
    """Return an AnalyticsConfig with test-safe values.

    Returns:
        An AnalyticsConfig instance suitable for unit tests.
    """
    return AnalyticsConfig.model_validate(
        {
            "clickhouse_host": "localhost",
            "clickhouse_port": 8443,
            "clickhouse_database": "test_db",
            "clickhouse_user": "default",
            "clickhouse_password": "test",
            "openai_api_key": "sk-test",
            "llm_provider": "openai",
            "llm_model_name": "gpt-4o-mini",
        }
    )


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Return a MagicMock that satisfies the BaseChatModel interface.

    The mock's ``ainvoke`` method returns a MagicMock with a ``content``
    attribute set to an empty string by default.  Tests should override
    ``mock_llm_provider.ainvoke.return_value.content`` with the desired
    response text before invoking the code under test.

    Returns:
        A MagicMock configured as a minimal BaseChatModel substitute.
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="{}"))
    mock.with_structured_output = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def mock_clickhouse_client() -> MagicMock:
    """Return a MagicMock simulating an async clickhouse_connect client.

    Returns:
        A MagicMock with async ``command`` and ``query`` methods.
    """
    client = MagicMock()
    client.command = AsyncMock(return_value=None)
    client.query = AsyncMock(return_value=MagicMock(result_rows=[]))
    return client
