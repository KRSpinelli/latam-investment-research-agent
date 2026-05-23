"""Constants for the analytics agent framework.

All magic values used across the analytics agent are centralised here.
Never use the literal strings or numbers directly in application code;
always import from this module.
"""

DEFAULT_EXPORT_ROW_LIMIT: int = 10_000
"""Default maximum number of rows written to a CSV export by the RAG query agent."""

PAGE_SEPARATOR: str = "\n--- PAGE BREAK ---\n"
"""Delimiter inserted between PDF pages by the document fetcher.

The numerical extractor splits on this string to reassemble page batches.
Both modules must use this constant — never the literal string.
"""

PAGE_BATCH_SIZE: int = 5
"""Number of PDF pages sent to the LLM in a single extraction request."""

MAX_CHARS_PER_BATCH: int = 80_000
"""Hard character limit applied to each extraction batch before sending to the LLM.

gpt-4o-mini's context window is 128k tokens (~4 chars/token ≈ 512k chars).
80k chars leaves ample room for the system prompt, function schema, and response.
When a page batch exceeds this limit it is truncated with a trailing notice so
the LLM knows the text was cut.
"""

MAX_EXTRACTION_RETRIES: int = 3
"""Maximum number of times the numerical extractor re-invokes the LLM after a validation error."""

CREATE_NEW_TABLE_SENTINEL: str = "__create_new__"
"""Sentinel returned by the table routing LLM when no existing table matches the dataset."""

MANDATORY_AUDIT_COLUMNS: tuple[str, ...] = (
    "source_reference",
    "ingestion_timestamp",
    "content_hash",
)
"""Column names reserved for audit purposes in every dynamically created ClickHouse table.

The LLM MUST NOT propose columns with these names in a RoutingDecision.proposed_schema.
The repository always prepends these columns regardless of what the LLM returns.
"""

CLICKHOUSE_TABLE_ENGINE: str = "MergeTree()"
"""ClickHouse table engine used for all dynamically created analytical tables."""

CLICKHOUSE_ORDER_BY_COLUMNS: tuple[str, ...] = (
    "source_reference",
    "content_hash",
    "ingestion_timestamp",
)
"""Column order used in the ORDER BY clause of all dynamically created ClickHouse tables."""

CLICKHOUSE_ALTER_MAX_RETRIES: int = 5
"""Maximum attempts for ``ALTER TABLE`` on ClickHouse Cloud when replicas are catching up."""

CLICKHOUSE_ALTER_RETRY_BASE_DELAY_SECONDS: float = 0.5
"""Base delay in seconds between retryable ClickHouse ``ALTER`` attempts (exponential backoff)."""

EXPORT_QUESTION_SLUG_MAX_LENGTH: int = 40
"""Maximum character length of the question slug used in CSV export filenames."""
