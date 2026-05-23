"""ClickHouse writer interface (implement with clickhouse-connect in integration step)."""

from typing import Protocol

from latam_investment_research_agent.agents.retrieval.schemas.clickhouse import (
    ClickHouseMetricRow,
    ClickHouseSignalRow,
)


class ClickHouseWriter(Protocol):
    def insert_signal_rows(self, rows: list[ClickHouseSignalRow]) -> int: ...

    def insert_metric_rows(self, rows: list[ClickHouseMetricRow]) -> int: ...


class InMemoryClickHouseWriter:
    """Stub for local dev and tests."""

    def __init__(self) -> None:
        self.signal_rows: list[ClickHouseSignalRow] = []
        self.metric_rows: list[ClickHouseMetricRow] = []

    def insert_signal_rows(self, rows: list[ClickHouseSignalRow]) -> int:
        self.signal_rows.extend(rows)
        return len(rows)

    def insert_metric_rows(self, rows: list[ClickHouseMetricRow]) -> int:
        self.metric_rows.extend(rows)
        return len(rows)
