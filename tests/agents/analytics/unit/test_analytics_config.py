"""Unit tests for AnalyticsConfig environment loading."""

from __future__ import annotations

import os

import pytest

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig


def test_analytics_config_ignores_unrelated_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AnalyticsConfig must not fail when a shared .env defines other app settings."""
    monkeypatch.setenv("CLICKHOUSE_HOST", "localhost")
    monkeypatch.setenv("CLICKHOUSE_DATABASE", "latam_research_test")
    monkeypatch.setenv("CLICKHOUSE_USER", "default")
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "secret")
    monkeypatch.setenv("NIMBLE_API_KEY", "nimble-key")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_PORT", "8000")

    config = AnalyticsConfig(_env_file=None)

    assert config.clickhouse_host == "localhost"
    assert config.clickhouse_database == "latam_research_test"
