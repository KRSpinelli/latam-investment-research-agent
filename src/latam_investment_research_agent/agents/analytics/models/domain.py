"""Domain models shared across the ingestion and RAG query agents.

These Pydantic v2 models serve as both data-transfer objects and as the
structured-output schemas submitted to the LLM.  Every field uses fully
spelled-out names — no abbreviations.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnDefinition(BaseModel):
    """Describes one column in a proposed new ClickHouse table schema.

    The LLM produces a list of these when ``RoutingDecision.routing_action``
    is ``"create"``.  The repository prepends the mandatory audit columns
    before creating the table; they MUST NOT appear here.

    Attributes:
        column_name: Snake_case name for the ClickHouse column.
        clickhouse_type: ClickHouse type string.  Monetary amounts MUST use
            ``Decimal(18,4)``; non-monetary ratios and percentages may use
            ``Float64``; text fields use ``String``.
        description: Human-readable description of what the column represents.
    """

    column_name: str = Field(
        description="Snake_case column name, no abbreviations."
    )
    clickhouse_type: str = Field(
        description=(
            "ClickHouse type string. Use Decimal(18,4) for monetary values, "
            "Float64 for ratios/percentages, String for text, "
            "DateTime64(3,'UTC') for timestamps."
        )
    )
    description: str = Field(
        description="What this column represents in the financial dataset."
    )


class ColumnInfo(BaseModel):
    """Describes one column as returned by ClickHouse DESCRIBE TABLE.

    Attributes:
        column_name: The column name as stored in ClickHouse.
        column_type: The ClickHouse type string for this column.
    """

    column_name: str
    column_type: str


class TableSchema(BaseModel):
    """The schema of one ClickHouse table, used by routing and RAG nodes.

    Attributes:
        table_name: The ClickHouse table name.
        columns: All columns in the table including audit columns.
    """

    table_name: str
    columns: list[ColumnInfo]


class RoutingDecision(BaseModel):
    """The LLM's routing decision for one extracted dataset.

    Attributes:
        target_table_name: An existing ClickHouse table name, or the sentinel
            string ``"__create_new__"`` (from ``constants.CREATE_NEW_TABLE_SENTINEL``)
            when no compatible table exists.
        routing_action: Whether to append to an existing table or create a new one.
        rationale: The LLM's explanation of its routing decision.  Logged but
            not returned to the caller.
        proposed_schema: Column definitions for a new table.  ``None`` when
            ``routing_action`` is ``"append"``.  MUST NOT include audit columns.
    """

    target_table_name: str = Field(
        description=(
            "Name of an existing ClickHouse table to append to, "
            "or '__create_new__' if no compatible table exists."
        )
    )
    routing_action: Literal["append", "create"] = Field(
        description="'append' to write to an existing table; 'create' to make a new one."
    )
    rationale: str = Field(
        description="Brief explanation of why this table was selected or why a new one is needed."
    )
    proposed_schema: list[ColumnDefinition] | None = Field(
        default=None,
        description=(
            "Column definitions for new table creation. "
            "Null when routing_action is 'append'. "
            "Must not include source_reference, ingestion_timestamp, or content_hash."
        ),
    )


class ExtractedDataset(BaseModel):
    """One semantically coherent numerical dataset extracted from a source document.

    Attributes:
        dataset_name: Human-readable name inferred by the LLM, e.g.
            ``"Annual Coffee Production by Region"``.
        context_labels: Surrounding text labels that describe the data's meaning.
        column_names: Column headers extracted from the table.
        rows: Rows as key-value mappings of column_name to value.
    """

    dataset_name: str = Field(
        description="Descriptive name for this dataset, inferred from surrounding context."
    )
    context_labels: list[str] = Field(
        description="Text labels from surrounding headers, captions, or notes."
    )
    column_names: list[str] = Field(
        description="Column headers for this dataset."
    )
    rows: list[dict[str, Any]] = Field(
        description="Rows as dicts mapping column_name to extracted value."
    )


class DatasetIngestionResult(BaseModel):
    """Records the outcome of successfully writing one dataset to ClickHouse.

    Attributes:
        dataset_name: Name of the extracted dataset.
        target_table_name: ClickHouse table where rows were written.
        routing_action: Whether the table was appended to or created.
        rows_written: Number of rows inserted after deduplication.
    """

    dataset_name: str
    target_table_name: str
    routing_action: Literal["append", "create"]
    rows_written: int


class DatasetIngestionFailure(BaseModel):
    """Records the outcome of a failed dataset write attempt.

    Attributes:
        dataset_name: Name of the extracted dataset that could not be written.
        error_detail: Exception message or error description.
    """

    dataset_name: str
    error_detail: str
