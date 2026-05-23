# Research: Document Ingestion & RAG Query Agent Framework

**Branch**: `001-document-ingestion-rag` | **Date**: 2026-05-23

---

## PDF Table Extraction Library

**Decision**: `pdfplumber`

**Rationale**: pdfplumber is purpose-built for financial table extraction from text-based PDFs.
It uses native PDF coordinates to detect table boundaries with high accuracy on structured
financial statements, production reports, and statistical appendices — the primary document types
for LATAM investment research. It is pure Python (no Java/Ghostscript dependency), MIT-licensed,
actively maintained, and exposes an `async`-compatible API.

**Alternatives considered**:
- `pymupdf` (fitz): Excellent for document rendering and text extraction, but its table detection
  is less specialized than pdfplumber's dedicated `extract_tables()` API. Better reserved for
  future OCR pipeline integration.
- `camelot`: Strong computer-vision-based table detection but requires Java (Tabula) or
  Ghostscript, adds significant operational overhead, and maintenance has slowed. Rejected.

---

## Web Page Scraping

**Decision**: `httpx` + `beautifulsoup4`

**Rationale**: httpx provides first-class async HTTP support (HTTP/1.1 and HTTP/2), which is
essential for the async LangGraph node architecture. BeautifulSoup4's CSS selector API cleanly
extracts `<table>` elements from financial statistics pages without requiring XPath knowledge.
Both libraries are MIT/Apache-2.0 licensed and actively maintained.

**Alternatives considered**:
- `lxml` directly: Faster raw parsing but XPath-centric API adds learning curve with no
  meaningful throughput benefit at the document volumes in scope.
- `playwright`: Required for JavaScript-rendered pages; explicitly deferred to a future version
  per the spec. Architecture does not preclude adding it later as a fallback document fetcher.

---

## LLM-Based Numerical Data Extraction

**Decision**: OpenAI structured outputs via `langchain_openai.ChatOpenAI` with Pydantic v2
strict-mode response schemas. Default model: `gpt-4o-mini`.

**Rationale**: Financial documents contain numerical data in varied formats (tables, inline
paragraphs, footnotes). Rule-based extraction is brittle across document styles. LLM extraction
with a strict Pydantic schema enforces valid JSON output, catches ambiguous values, and allows
the model to infer contextual labels (row/column headers) that pure regex cannot.

Key extraction design choices:
- Use `Decimal` (not `float`) for all monetary amounts to avoid floating-point precision loss.
- Include explicit instructions for locale-aware number parsing (period vs. comma as decimal
  separator) in the system prompt.
- Implement retry logic: if the model returns a schema-invalid response, re-invoke with the
  validation error appended to the prompt (max 3 retries).
- Chunk large documents: process pdfplumber pages in batches of 5 to stay within context limits.

---

## LLM Provider Abstraction

**Decision**: `langchain_core.language_models.BaseChatModel` as the provider interface.
Factory function `create_llm_provider()` in `providers/llm_provider.py` reads `LLM_PROVIDER`
and `LLM_MODEL_NAME` environment variables and returns the appropriate `BaseChatModel`.

**Rationale**: LangGraph already depends on `langchain_core`; using `BaseChatModel` as the
abstraction boundary requires zero additional dependencies. Swapping providers (e.g., from
OpenAI to Anthropic) requires only changing two environment variables and installing the
corresponding `langchain_*` integration package — no code changes needed.

Default: `langchain_openai.ChatOpenAI(model="gpt-4o-mini", temperature=0)`

---

## LLM-Based Table Routing

**Decision**: Dedicated LangGraph routing node that passes (a) the extracted dataset's name,
context labels, and column structure alongside (b) a list of existing ClickHouse table names
and their column schemas to `gpt-4o-mini`. The model returns a structured routing decision:
target table name or `"__create_new__"` sentinel, plus a rationale string.

**Rationale**: Financial data categories (e.g., "annual production volumes", "export revenues by
destination") do not map predictably to table names via string matching. LLM judgment handles
synonym matching, cross-language labels (Portuguese/English), and partial schema overlap.

**Alternatives considered**:
- Rule-based fuzzy matching: Insufficient for cross-language document labels (Portuguese
  headers in the source document, English table names in the database).
- Embedding similarity: Adds vector store dependency with no clear accuracy advantage for the
  narrow schema-matching problem at this scale.

---

## ClickHouse Schema Strategy

**Decision**: `clickhouse-connect` (official Python driver). Tables use `MergeTree()` engine.
Dynamic table creation via `CREATE TABLE IF NOT EXISTS`. Schema evolution via
`ALTER TABLE {table} ADD COLUMN {col} {type} DEFAULT {default}`.

**Deduplication**: Content hash computed as `hashlib.sha256(canonical_row_string).hexdigest()`
where `canonical_row_string = json.dumps(row, sort_keys=True, default=str)`. Hash stored in a
`content_hash String` column. Primary key includes `(source_reference, content_hash)`.
Insert-time deduplication: `INSERT INTO {table} SELECT ... WHERE (source_reference, content_hash)
NOT IN (SELECT source_reference, content_hash FROM {table})`.

Every dynamically created table includes mandatory audit columns:
- `source_reference String` — URL or file path of the source document
- `ingestion_timestamp DateTime64(3, 'UTC')` — UTC timestamp of insert
- `content_hash String` — row-level deduplication key

**Rationale**: MergeTree is the correct engine for analytical OLAP workloads. Insert-time
deduplication (NOT IN check) is simpler to reason about than eventual merge-time deduplication
(ReplacingMergeTree), which has asynchronous semantics that complicate correctness guarantees
in a financial audit context.

---

## CSV Export

**Decision**: `polars` — `polars.from_dicts(records).write_csv(file_path)`

**Rationale**: Polars is columnar-native and significantly faster than pandas for large result
sets. It produces standards-compliant CSV output. The `from_dicts()` constructor accepts the
list-of-dicts format returned by `clickhouse-connect` query results without transformation.
Default export row limit: 10,000 rows (caller-configurable via `RAGQueryInput.export_row_limit`).

---

## Async Architecture

**Decision**: Full async throughout — `async def` node functions, `httpx.AsyncClient` for HTTP,
`asyncio`-compatible ClickHouse queries via `clickhouse-connect`'s async client.

**Rationale**: LangGraph nodes can be `async def`; async I/O eliminates blocking during PDF
fetches, web requests, LLM API calls, and ClickHouse writes — all of which are network-bound.
This is essential to meet SC-001 (100-page PDF ingested in ≤5 minutes) and SC-004 (RAG query
returns in ≤30 seconds).
