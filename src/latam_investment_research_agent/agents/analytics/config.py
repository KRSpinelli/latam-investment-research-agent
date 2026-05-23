"""Configuration for the analytics agent framework.

All settings are sourced exclusively from environment variables so that no
credentials are embedded in source code.  Copy `.env.sample` to `.env` and
fill in the values before running the agents.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsConfig(BaseSettings):
    """Typed configuration loaded from environment variables.

    All ClickHouse connection settings and LLM provider selection are read at
    instantiation time.  A missing required variable raises a ``ValidationError``
    immediately, rather than at the point of first use.

    Example:
        config = AnalyticsConfig()
        client = clickhouse_connect.get_client(
            host=config.clickhouse_host,
            port=config.clickhouse_port,
            database=config.clickhouse_database,
            username=config.clickhouse_user,
            password=config.clickhouse_password,
        )
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    clickhouse_host: str
    clickhouse_port: int = 8443
    clickhouse_database: str
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_verify_tls: bool = True

    openai_api_key: str = ""
    llm_provider: str = "openai"
    llm_model_name: str = "gpt-4o-mini"

    clickhouse_max_concurrent_queries: int = 8

    test_clickhouse_host: str = "localhost"
    test_clickhouse_port: int = 8443
    test_clickhouse_database: str = "latam_research_test"
    test_clickhouse_user: str = "default"
    test_clickhouse_password: str = ""
