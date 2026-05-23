"""Factory for creating an async ClickHouse client from AnalyticsConfig.

The graph factories (build_ingestion_graph, build_rag_query_graph) accept an
injected ``clickhouse_client`` for testing.  In production, call
``create_clickhouse_client(config)`` before building the graph and pass the
result in explicitly.

Example::

    config = AnalyticsConfig()
    client = await create_clickhouse_client(config)
    graph = build_ingestion_graph(config=config, clickhouse_client=client)
    result = await graph.ainvoke({"source_reference": url})
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import clickhouse_connect

from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig

logger = logging.getLogger(__name__)


async def create_clickhouse_client(config: AnalyticsConfig) -> Any:
    """Create and return an async ClickHouse client from the given config.

    Uses ``clickhouse_connect.get_async_client`` with the host, port,
    database, username, and password from ``config``.  The ``secure``
    flag is inferred from the port number: 8443 is treated as HTTPS,
    all other ports as plain HTTP.

    Args:
        config: Analytics configuration containing ClickHouse connection settings.

    Returns:
        An async clickhouse_connect client instance ready for ``await client.query()``.
    """
    secure = config.clickhouse_port == 8443
    logger.info(
        "Connecting to ClickHouse at %s:%d (database: %s, secure: %s, verify_tls: %s)",
        config.clickhouse_host,
        config.clickhouse_port,
        config.clickhouse_database,
        secure,
        config.clickhouse_verify_tls,
    )
    client_kwargs: dict[str, Any] = {
        "host": config.clickhouse_host,
        "port": config.clickhouse_port,
        "database": config.clickhouse_database,
        "username": config.clickhouse_user,
        "password": config.clickhouse_password,
        "secure": secure,
        "verify": config.clickhouse_verify_tls,
    }
    # macOS Python builds often lack OS CA certs in the default SSL context;
    # clickhouse-connect resolves ca_cert="certifi" to the certifi CA bundle.
    if secure and config.clickhouse_verify_tls:
        client_kwargs["ca_cert"] = "certifi"

    client = await clickhouse_connect.get_async_client(**client_kwargs)
    logger.info("ClickHouse connection established")
    return client


async def close_clickhouse_client(client: Any) -> None:
    """Close an async ClickHouse client and release its HTTP connection pool.

    Args:
        client: An async client returned by ``create_clickhouse_client``.
    """
    close_method = getattr(client, "close", None)
    if close_method is None:
        return
    await close_method()
    # Yield so aiohttp can finish closing connectors on the event loop.
    await asyncio.sleep(0)


@asynccontextmanager
async def managed_clickhouse_client(
    config: AnalyticsConfig,
) -> AsyncIterator[Any]:
    """Open a ClickHouse client for a scoped block and close it on exit.

    Args:
        config: Analytics configuration containing ClickHouse connection settings.

    Yields:
        An async clickhouse_connect client instance.

    Example:
        async with managed_clickhouse_client(config) as client:
            await client.query("SELECT 1")
    """
    client = await create_clickhouse_client(config)
    try:
        yield client
    finally:
        await close_clickhouse_client(client)
