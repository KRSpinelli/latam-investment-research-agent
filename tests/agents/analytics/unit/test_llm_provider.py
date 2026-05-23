"""Unit tests for the LLM provider factory.

Tests MUST be run and confirmed failing before the implementation in
providers/llm_provider.py is written.
"""


import pytest

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig
from latam_investment_research_agent.agents.analytics.providers.llm_provider import (
    create_llm_provider,
)


def _make_config(**overrides: str | int) -> AnalyticsConfig:
    """Build an AnalyticsConfig suitable for unit tests.

    Args:
        **overrides: Field values to override on the config.

    Returns:
        An AnalyticsConfig instance with test-safe defaults.
    """
    defaults = {
        "clickhouse_host": "localhost",
        "clickhouse_port": 8443,
        "clickhouse_database": "test_db",
        "clickhouse_user": "default",
        "clickhouse_password": "test",
        "openai_api_key": "sk-test-key",
        "llm_provider": "openai",
        "llm_model_name": "gpt-4o-mini",
    }
    defaults.update(overrides)
    return AnalyticsConfig.model_validate(defaults)


def test_create_llm_provider_returns_base_chat_model_for_openai() -> None:
    """create_llm_provider returns a BaseChatModel instance for the openai provider."""
    from langchain_core.language_models import BaseChatModel

    config = _make_config(llm_provider="openai")
    provider = create_llm_provider(config)
    assert isinstance(provider, BaseChatModel)


def test_create_llm_provider_uses_configured_model_name() -> None:
    """create_llm_provider passes the model name from config to the LLM."""
    config = _make_config(llm_provider="openai", llm_model_name="gpt-4o-mini")
    provider = create_llm_provider(config)
    # ChatOpenAI exposes the model name via .model_name attribute
    assert getattr(provider, "model_name", None) == "gpt-4o-mini"


def test_create_llm_provider_raises_for_unknown_provider() -> None:
    """create_llm_provider raises ValueError for an unrecognised provider name."""
    config = _make_config(llm_provider="unknown_provider_xyz")
    with pytest.raises(ValueError, match="unknown_provider_xyz"):
        create_llm_provider(config)
