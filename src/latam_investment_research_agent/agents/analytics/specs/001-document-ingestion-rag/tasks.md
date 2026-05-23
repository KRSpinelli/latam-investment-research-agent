# Tasks: Document Ingestion & RAG Query Agent Framework

**Input**: Design documents from `specs/001-document-ingestion-rag/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**TDD Gate** (Constitution Principle II — NON-NEGOTIABLE):
Every test task MUST be run and confirmed **failing** before the implementation task it covers
begins. Do not proceed to implementation until the red state is verified.

**Key artifact cross-references** (read at the step indicated — do not skip):
- State schemas → `data-model.md`
- Node sequences & error behaviour → `contracts/ingestion_graph.md`, `contracts/rag_query_graph.md`
- Library choices & prompt design → `research.md`
- Build order & cross-references → `plan.md § Implementation Sequence`
- Env vars → `.env.sample` (created in T002)

---

## Format: `[ID] [P?] [Story?] Description — file path`

- **[P]**: Parallelizable (different files, no unresolved dependencies)
- **[Story]**: US1 = PDF Ingestion, US2 = Web Ingestion, US3 = Table Routing, US4 = RAG Query
- Tests MUST be written and fail before the implementation task they guard

---

## Phase 1: Setup

**Purpose**: Project scaffolding — blocks everything else.

- [x] T001 Create Python package `__init__.py` files for all source directories: `graph/`, `nodes/`, `nodes/ingestion/`, `nodes/rag/`, `models/`, `repositories/`, `services/`, `providers/` — each as an empty `__init__.py` under `src/latam_investment_research_agent/agents/analytics/`
- [x] T002 Create `.env.sample` with all required env vars: `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `OPENAI_API_KEY`, `LLM_PROVIDER` (default `openai`), `LLM_MODEL_NAME` (default `gpt-4o-mini`) — see `contracts/ingestion_graph.md § Required Environment Variables`
- [x] T003 [P] Create `pyproject.toml` declaring all dependencies: `langgraph`, `langchain-core`, `langchain-openai`, `clickhouse-connect`, `pdfplumber`, `httpx`, `beautifulsoup4`, `polars`, `pydantic>=2`, `python-dotenv`; dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff` — see `plan.md § Technical Context`
- [x] T004 [P] Create `constants.py` with: `DEFAULT_EXPORT_ROW_LIMIT = 10_000`, `PAGE_BATCH_SIZE = 5`, `MAX_EXTRACTION_RETRIES = 3`, `CREATE_NEW_TABLE_SENTINEL = "__create_new__"`, `MANDATORY_AUDIT_COLUMNS` tuple of `("source_reference", "ingestion_timestamp", "content_hash")` — see `data-model.md § ClickHouse Table Conventions`
- [x] T005 [P] Create `config.py` with `AnalyticsConfig(BaseSettings)` reading: `clickhouse_host`, `clickhouse_port` (int, default 8443), `clickhouse_database`, `clickhouse_user`, `clickhouse_password`, `openai_api_key`, `llm_provider` (default `"openai"`), `llm_model_name` (default `"gpt-4o-mini"`) from environment — see `.env.sample`
- [x] T006 [P] Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/performance/__init__.py`; create `pytest.ini` or `pyproject.toml [tool.pytest]` with `asyncio_mode = "auto"` and `cov` config requiring 90% minimum

**Checkpoint**: `pip install -e ".[dev]"` (or `uv sync`) succeeds with zero errors.

---

## Phase 2: Foundational

**Purpose**: Domain models, repositories, and shared test infrastructure — blocks all user story phases. Complete this phase entirely before beginning any user story phase.

### Domain Models (no dependencies — build first)

- [x] T007 [P] Create `models/domain.py` defining Pydantic v2 models and TypedDicts: `ColumnDefinition` (column_name, clickhouse_type — monetary MUST use `Decimal(18,4)` not `Float64`, description), `ColumnInfo` (column_name, column_type), `TableSchema` (table_name, columns: list[ColumnInfo]), `RoutingDecision` (target_table_name, routing_action: Literal["append","create"], rationale, proposed_schema: list[ColumnDefinition] | None), `DatasetIngestionResult` (dataset_name, target_table_name, routing_action, rows_written), `DatasetIngestionFailure` (dataset_name, error_detail), `ExtractedDataset` (dataset_name, context_labels, column_names, rows: list[dict[str,Any]]) — see `data-model.md § LangGraph State Schemas`
- [x] T008 [P] Create `models/ingestion_state.py` with TypedDicts: `IngestionState` (source_reference, raw_content: str|None, extracted_datasets, current_dataset_index: int, ingestion_results, ingestion_failures, error: str|None), `IngestionGraphInput` (source_reference), `IngestionSummary` (source_reference, total_datasets_found, datasets_succeeded, datasets_failed) — see `data-model.md § IngestionState`
- [x] T009 [P] Create `models/rag_state.py` with TypedDicts: `RAGQueryState` (natural_language_question, export_row_limit: int, available_table_schemas, selected_table_names, assembled_sql_queries, query_result_records, export_file_path: str|None, rationale: str|None, error: str|None), `RAGQueryInput` (natural_language_question, export_row_limit: int = 10_000, export_directory: str = "./exports"), `RAGQueryOutput` (export_file_path, rationale, sql_queries_used, row_count: int, was_truncated: bool) — see `data-model.md § RAGQueryState`

### LLM Provider

- [x] T010 [P] Write failing unit tests in `tests/unit/test_llm_provider.py`: test that `create_llm_provider()` returns a `BaseChatModel` instance for `LLM_PROVIDER=openai`; test that unknown provider raises `ValueError`; run tests and confirm red — see `research.md § LLM Provider Abstraction`
- [x] T011 [P] Implement `providers/llm_provider.py` with `create_llm_provider(config: AnalyticsConfig) -> BaseChatModel` factory: returns `ChatOpenAI(model=config.llm_model_name, temperature=0)` for `config.llm_provider == "openai"`; raises `ValueError` for unknown providers — verify T010 tests go green

### Repositories

- [x] T012 [P] Write failing unit tests in `tests/unit/test_schema_repository.py`: mock `clickhouse_connect` client; test `get_all_table_schemas()` returns empty list when no tables; test it maps `DESCRIBE TABLE` results into `list[TableSchema]` correctly — confirm red
- [x] T013 [P] Write failing unit tests in `tests/unit/test_clickhouse_repository.py`: test `create_table()` issues correct `CREATE TABLE IF NOT EXISTS` SQL with `MergeTree()` engine, `ORDER BY (source_reference, content_hash, ingestion_timestamp)`, and includes all three mandatory audit columns; test `insert_rows_deduplicated()` uses `NOT IN (SELECT source_reference, content_hash FROM {table})` dedup pattern; test `alter_table_add_columns()` generates correct `ALTER TABLE ADD COLUMN` SQL — confirm red — see `research.md § ClickHouse Schema Strategy`, `data-model.md § ClickHouse Table Conventions`
- [x] T014 Implement `repositories/schema_repository.py` with async `get_all_table_schemas(client: AsyncClient) -> list[TableSchema]` — queries `SHOW TABLES` then `DESCRIBE TABLE {name}` for each, maps to `TableSchema` and `ColumnInfo`; Google docstring required — verify T012 tests go green
- [x] T015 Implement `repositories/clickhouse_repository.py` with async methods: `create_table(client, table_name: str, columns: list[ColumnDefinition]) -> None` (prepends mandatory audit columns, never lets LLM-proposed columns include audit columns), `alter_table_add_columns(client, table_name: str, new_columns: list[ColumnDefinition]) -> None`, `insert_rows_deduplicated(client, table_name: str, rows: list[dict[str, Any]], source_reference: str) -> int` (computes per-row `content_hash = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()` — full 64-char digest, no truncation — returns count of rows actually written) — verify T013 tests go green — see `plan.md § Deduplication Strategy`

### Shared Test Infrastructure

- [x] T016 Create `tests/conftest.py` with shared pytest fixtures: `mock_llm_provider` (returns a `MagicMock` conforming to `BaseChatModel` interface), `clickhouse_test_client` (connects to a local ClickHouse test instance using env vars prefixed `TEST_`), `test_database_cleanup` (drops all tables in the test database after each integration test session)

**Checkpoint**: `pytest tests/unit/ -v` passes all unit tests. Foundation is ready for user story phases.

---

## Phase 3: User Story 1 + User Story 3 — PDF Ingestion with Smart Table Routing (Priority: P1)

**Goal**: Ingest a financial PDF from a URL, extract numerical datasets via LLM, route each dataset to an existing or new ClickHouse table via LLM judgment, persist with audit columns, return a structured ingestion summary.

**US3 note**: Smart table routing (US3) is architecturally inseparable from US1 — routing is exercised on every ingestion run. Both stories share this phase.

**Independent Test**: Invoke `ingestion_graph` with the Cooxupé PDF URL. Verify ClickHouse contains at least one table with rows where `source_reference` equals the URL, `content_hash` is non-null, and values match the PDF.

### TDD — Write Tests First (confirm red before T023)

- [x] T017 [P] [US1] Write failing unit tests in `tests/unit/test_document_fetcher.py` for PDF path: test `fetch_document(url)` returns non-empty string for a valid PDF URL (mock `httpx.AsyncClient`); test it raises `DocumentFetchError` on 4xx/5xx; test it falls back gracefully on corrupt PDF — confirm red — see `research.md § PDF Table Extraction Library`
- [x] T018 [P] [US1] Write failing unit tests in `tests/unit/test_numerical_extractor.py`: test `extract_datasets(text, llm)` returns `list[ExtractedDataset]`; test that page batching sends batches of `PAGE_BATCH_SIZE=5` pages; test retry logic invokes LLM up to `MAX_EXTRACTION_RETRIES=3` on schema validation failure; test returns empty list (not error) when no numerical data found — confirm red — see `research.md § LLM-Based Numerical Data Extraction`, `data-model.md § ExtractedDataset`
- [x] T019 [P] [US3] Write failing unit tests in `tests/unit/test_table_router.py`: test `route_dataset(dataset, existing_schemas, llm)` returns `RoutingDecision` with `routing_action="append"` when a compatible table exists; test returns `routing_action="create"` with non-null `proposed_schema` when no compatible table; test that `proposed_schema` never contains audit column names (`source_reference`, `ingestion_timestamp`, `content_hash`); test uses `CREATE_NEW_TABLE_SENTINEL` constant for the sentinel value — confirm red — see `research.md § LLM-Based Table Routing`, `data-model.md § RoutingDecision`
- [x] T020 [US1] Write failing integration tests in `tests/integration/test_ingestion_graph.py`: test US1 acceptance scenario (PDF URL → ClickHouse rows with correct `source_reference`); test idempotency (run same URL twice → zero duplicate rows); test partial failure (mock one write failure → `datasets_failed` non-empty, succeeded rows still present) — confirm red — see `spec.md § User Story 1 Acceptance Scenarios`, `contracts/ingestion_graph.md § Error Behaviour`

### Implementation

- [x] T021 [US1] Implement `services/document_fetcher.py` with `async def fetch_document(source_reference: str) -> str` — detect PDF (URL ending in `.pdf` or Content-Type `application/pdf`) vs HTML; for PDF: `httpx.AsyncClient.get()` then `pdfplumber.open(BytesIO(content)).pages[i].extract_text()`; raise `DocumentFetchError` (custom exception defined in this module) on HTTP errors or corrupt file; Google docstring required — verify T017 tests go green — see `research.md § PDF Table Extraction Library`
- [x] T022 [US1] Implement `services/numerical_extractor.py` with `async def extract_datasets(raw_text: str, llm: BaseChatModel) -> list[ExtractedDataset]` — split text into page batches of `PAGE_BATCH_SIZE`; for each batch: invoke LLM with structured Pydantic v2 response schema targeting `ExtractedDataset`; system prompt MUST include locale-aware number parsing instructions (period vs comma as decimal separator); monetary fields in Pydantic schema MUST use `Decimal` not `float`; retry up to `MAX_EXTRACTION_RETRIES` on `ValidationError` appending the error message to prompt; Google docstring required — verify T018 tests go green — see `research.md § LLM-Based Numerical Data Extraction`, `plan.md § LLM-Based Numerical Extraction`
- [x] T023 [US3] Implement `services/table_router.py` with `async def route_dataset(dataset: ExtractedDataset, existing_schemas: list[TableSchema], llm: BaseChatModel) -> RoutingDecision` — builds prompt with dataset metadata and all existing table names + columns; invokes LLM with Pydantic structured output targeting `RoutingDecision`; ensures `proposed_schema` never includes audit column names (validated post-LLM-call, raise `ValueError` if violated); uses `constants.CREATE_NEW_TABLE_SENTINEL` for the sentinel string; Google docstring required — verify T019 tests go green — see `research.md § LLM-Based Table Routing`, `plan.md § LLM-Based Table Routing`
- [x] T024 [P] [US1] Implement `nodes/ingestion/fetch_document_node.py` with `async def fetch_document_node(state: IngestionState, fetcher: DocumentFetcher) -> dict` — calls `fetcher.fetch_document(state["source_reference"])`; returns `{"raw_content": text}` on success or `{"error": str(exc)}` on failure; Google docstring required — see `data-model.md § IngestionState`, `contracts/ingestion_graph.md § Node Sequence`
- [x] T025 [P] [US1] Implement `nodes/ingestion/extract_numerical_data_node.py` with `async def extract_numerical_data_node(state: IngestionState, extractor: NumericalExtractor) -> dict` — calls `extractor.extract_datasets(state["raw_content"])`; returns `{"extracted_datasets": datasets, "current_dataset_index": 0}`; returns `{"extracted_datasets": [], "current_dataset_index": 0}` if `state["raw_content"]` is None — see `data-model.md § ExtractedDataset`
- [x] T026 [US3] Implement `nodes/ingestion/route_dataset_node.py` with `async def route_dataset_node(state: IngestionState, router: TableRouter, schema_repo: SchemaRepository, client: AsyncClient) -> dict` — fetches `state["extracted_datasets"][state["current_dataset_index"]]`; calls `schema_repo.get_all_table_schemas(client)` then `router.route_dataset(dataset, schemas)`; stores routing decision on state; returns dict with routing decision fields — see `data-model.md § RoutingDecision`, `plan.md § LLM-Based Table Routing`
- [x] T027 [US1] Implement `nodes/ingestion/write_to_clickhouse_node.py` with `async def write_to_clickhouse_node(state: IngestionState, repo: ClickhouseRepository, client: AsyncClient) -> dict` — uses routing decision to call `repo.create_table()` or `repo.alter_table_add_columns()` + `repo.insert_rows_deduplicated()`; on success: appends `DatasetIngestionResult` to `ingestion_results`; on exception: appends `DatasetIngestionFailure` (never re-raises); increments `current_dataset_index`; Google docstring required — see `plan.md § ClickHouse Repository: Schema Evolution`, `plan.md § Deduplication Strategy`
- [x] T028 [US1] Implement `nodes/ingestion/build_ingestion_summary_node.py` with `async def build_ingestion_summary_node(state: IngestionState) -> dict` — compiles `IngestionSummary` from `state["ingestion_results"]`, `state["ingestion_failures"]`, `state["source_reference"]`; sets `total_datasets_found = len(state["extracted_datasets"])`; returns `{"ingestion_summary": summary}` — see `data-model.md § IngestionSummary`
- [x] T029 [US1] Assemble `graph/ingestion_graph.py` — build `StateGraph(IngestionState)`; add all five ingestion nodes (inject dependencies via node factory functions or `functools.partial`); add conditional edge after `write_to_clickhouse_node`: route back to `route_dataset_node` while `current_dataset_index < len(extracted_datasets)`, else route to `build_ingestion_summary_node`; add error-state conditional edge after `fetch_document_node`: if `error` is set route directly to `build_ingestion_summary_node`; compile to `ingestion_graph` module-level singleton — see `plan.md § LangGraph Graph Compilation`, `plan.md § Ingestion Graph: Dataset Loop Pattern`, `contracts/ingestion_graph.md`

**Checkpoint**: `pytest tests/integration/test_ingestion_graph.py -v` passes. US1 + US3 independently functional.

---

## Phase 4: User Story 4 — RAG Query Agent (Priority: P1)

**Goal**: Accept a natural-language question, introspect ClickHouse schema, assemble SELECT-only SQL, export results to a timestamped CSV via Polars, and return the file path, rationale, and exact SQL used.

**Independent Test**: After ingesting the Cooxupé PDF, invoke `rag_query_graph` with "What were total export revenues by year?". Verify a CSV file exists at the returned path, contains year and revenue columns, and the returned SQL is valid reproducible `SELECT` syntax.

### TDD — Write Tests First (confirm red before T035)

- [x] T030 [P] [US4] Write failing unit tests in `tests/unit/test_query_assembler.py`: test `assemble_queries(question, schemas, llm)` returns a non-empty `list[str]`; test that every returned string starts with `SELECT` (case-insensitive); test that a query not starting with `SELECT` is rejected/excluded from the returned list — confirm red — see `plan.md § RAG Query: SELECT-Only Guard`
- [x] T031 [P] [US4] Write failing integration tests in `tests/integration/test_rag_query_graph.py`: test US4 acceptance scenario (question → CSV file path returned, file exists, row count > 0, SQL queries returned); test empty-result case returns rationale "No relevant data found" and no file; test truncation: when results exceed `export_row_limit`, `was_truncated=True` in output and rationale mentions truncation — confirm red — see `spec.md § User Story 4 Acceptance Scenarios`, `contracts/rag_query_graph.md § Error Behaviour`

### Implementation

- [x] T032 [US4] Implement `services/query_assembler.py` with `async def assemble_queries(question: str, selected_schemas: list[TableSchema], llm: BaseChatModel) -> list[str]` — builds prompt with selected table schemas and the natural-language question; instructs LLM to return only `SELECT` statements compatible with ClickHouse SQL; validates each returned query string starts with `SELECT` (stripped, case-insensitive); silently discards non-SELECT queries and logs a warning; Google docstring required — verify T030 tests go green — see `plan.md § RAG Query: SELECT-Only Guard`
- [x] T033 [P] [US4] Implement `nodes/rag/introspect_schema_node.py` with `async def introspect_schema_node(state: RAGQueryState, schema_repo: SchemaRepository, client: AsyncClient) -> dict` — calls `schema_repo.get_all_table_schemas(client)`; returns `{"available_table_schemas": schemas}`; sets `{"error": "No tables found"}` if result is empty — see `data-model.md § RAGQueryState`
- [x] T034 [P] [US4] Implement `nodes/rag/select_relevant_tables_node.py` with `async def select_relevant_tables_node(state: RAGQueryState, llm: BaseChatModel) -> dict` — passes `state["natural_language_question"]` and table names + column summaries to LLM; returns `{"selected_table_names": [...]}`; if no tables selected returns `{"selected_table_names": [], "error": "No relevant tables found"}` — see `data-model.md § RAGQueryState`
- [x] T035 [US4] Implement `nodes/rag/assemble_queries_node.py` with `async def assemble_queries_node(state: RAGQueryState, assembler: QueryAssembler) -> dict` — filters `state["available_table_schemas"]` to only selected tables; calls `assembler.assemble_queries()`; returns `{"assembled_sql_queries": queries}`; each query MUST include `LIMIT {state["export_row_limit"]}` — see `contracts/rag_query_graph.md § Node Sequence`
- [x] T036 [US4] Implement `nodes/rag/execute_queries_node.py` with `async def execute_queries_node(state: RAGQueryState, client: AsyncClient) -> dict` — re-validates each query starts with `SELECT` before execution (never trust previous validation alone); executes each query; merges result rows; if total rows exceed `state["export_row_limit"]` truncates and sets `was_truncated=True`; on per-query execution failure logs error and continues with remaining queries; returns `{"query_result_records": records, "was_truncated": bool}` — see `contracts/rag_query_graph.md § Read-Only Guarantee`
- [x] T037 [US4] Implement `nodes/rag/export_results_node.py` with `async def export_results_node(state: RAGQueryState) -> dict` — if `state["query_result_records"]` is empty returns `{"export_file_path": None}`; otherwise: generates filename `{YYYYMMDD_HHMMSS}_{question_slug}.csv` where `question_slug` is first 40 chars of question lowercased with non-alphanumeric replaced by `_`; creates export directory if not exists; calls `polars.from_dicts(records).write_csv(path)`; returns `{"export_file_path": str(abs_path)}` — see `contracts/rag_query_graph.md § CSV File Naming`, `research.md § CSV Export`
- [x] T038 [US4] Implement `nodes/rag/build_rag_response_node.py` with `async def build_rag_response_node(state: RAGQueryState) -> dict` — if `export_file_path` is None returns `RAGQueryOutput` with rationale "No relevant data found for this question" and empty queries list; otherwise assembles full `RAGQueryOutput`; if `was_truncated` is True appends truncation note to rationale — see `data-model.md § RAGQueryOutput`
- [x] T039 [US4] Assemble `graph/rag_query_graph.py` — build `StateGraph(RAGQueryState)`; add six RAG nodes in linear sequence; add error-state conditional edge after `introspect_schema_node` (if error set, route to `build_rag_response_node`); add conditional edge after `select_relevant_tables_node` (if no tables selected, route to `build_rag_response_node`); compile to `rag_query_graph` module-level singleton — see `plan.md § LangGraph Graph Compilation`, `contracts/rag_query_graph.md`

**Checkpoint**: `pytest tests/integration/test_rag_query_graph.py -v` passes. US4 independently functional. Run the quickstart scenario from `quickstart.md § 4. Query the Database` and verify end-to-end.

---

## Phase 5: User Story 2 — Web Page Ingestion (Priority: P2)

**Goal**: Extend the ingestion pipeline to accept a static web page URL, extract HTML tables containing numerical data, and store them in ClickHouse using the same routing and audit logic as PDF ingestion.

**Independent Test**: Invoke `ingestion_graph` with a public financial statistics URL. Verify ClickHouse contains rows with `source_reference` equal to that URL and extracted values match the page content.

### TDD — Write Tests First (confirm red before T041)

- [x] T040 [US2] Extend `tests/unit/test_document_fetcher.py` with HTML-specific tests: test `fetch_document(url)` returns extracted text from HTML `<table>` elements when Content-Type is `text/html`; test that non-table HTML content returns an empty string (not an error); test that a 404 response raises `DocumentFetchError` — confirm new tests are red before T041

### Implementation

- [x] T041 [US2] Extend `services/document_fetcher.py` to handle HTML sources — when Content-Type is `text/html`: use `BeautifulSoup(content, "html.parser")`; extract all `<table>` elements; convert each table's rows/headers to plain text representation concatenated with newlines; return combined text; leave PDF logic entirely unchanged — verify T040 tests go green — see `research.md § Web Page Scraping`
- [x] T042 [US2] Add web page integration scenario to `tests/integration/test_ingestion_graph.py`: test that a static HTML page URL is ingested through the unchanged ingestion graph (no graph code changes needed — `document_fetcher` handles the routing); confirm `source_reference` in ClickHouse equals the web page URL

**Checkpoint**: All ingestion integration tests pass including the web page scenario. US2 functional through the existing graph.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, performance validation, and constitution compliance verification.

- [x] T043 Create `tests/performance/test_ingestion_performance.py` — benchmark ingestion of a 100-page financial PDF end-to-end; assert total elapsed time ≤ 300 seconds (SC-001); use `pytest-benchmark` or `time.monotonic()` with assertion — see `spec.md § SC-001`
- [x] T044 [P] Run `mypy --strict src/latam_investment_research_agent/agents/analytics/` — resolve all type errors until zero remain; pay particular attention to `TypedDict` field optionality and `list[dict[str, Any]]` annotations
- [x] T045 [P] Run `ruff check src/ tests/ --fix` followed by `ruff format src/ tests/` — resolve all remaining violations; verify `ruff check` exits 0
- [x] T046 [P] Run `pytest --cov=latam_investment_research_agent.agents.analytics --cov-report=term-missing --cov-fail-under=90` — identify any modules below 90% and add targeted unit tests until threshold is met (SC-002 coverage proxy)
- [x] T047 [P] Audit all public functions and methods across `services/`, `repositories/`, `nodes/`, `providers/`, `graph/` — add Google-style docstrings to any public function missing one; verify no variable name abbreviations remain (e.g., `ch_conn` → `clickhouse_connection`, `sig` → `investment_signal`) — Constitution Principle V
- [x] T048 Validate quickstart.md end-to-end: follow `quickstart.md` steps verbatim in a clean environment; verify ingestion completes, RAG query produces a CSV file, and the swap-LLM-provider section works by confirming `create_llm_provider()` returns a different `BaseChatModel` subclass when `LLM_PROVIDER` is changed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user story phases
- **US1+US3 (Phase 3)**: Depends on Phase 2 — no dependency on US4 or US2
- **US4 (Phase 4)**: Depends on Phase 2 — no dependency on US1+US3 or US2 (can run in parallel with Phase 3 if staffed)
- **US2 (Phase 5)**: Depends on Phase 3 completion (extends `document_fetcher.py`)
- **Polish (Phase 6)**: Depends on Phases 3, 4, and 5

### User Story Dependencies

- **US1+US3 (P1)**: Foundational complete → implement
- **US4 (P1)**: Foundational complete → implement (parallel with US1+US3)
- **US2 (P2)**: US1+US3 complete → extend `document_fetcher.py` only

### Within Each Phase

- TDD tests MUST be written and fail before implementation begins
- Domain models (T007–T009) before repositories (T012–T015)
- Repositories before nodes that call ClickHouse
- Services before nodes that call them
- All nodes before graph assembly

### Parallel Opportunities

- T003, T004, T005, T006 — all Phase 1, different files, run in parallel
- T007, T008, T009, T010 — all Phase 2 models/provider, different files, run in parallel
- T012, T013 — test files for two different repositories, run in parallel
- T014, T015 — implementations after their respective tests fail (can start T014 while T013 is still being written)
- T017, T018, T019 — three independent test files in Phase 3, run in parallel
- T030, T031 — two independent test files in Phase 4, run in parallel
- T033, T034 — two independent RAG node implementations, run in parallel
- T044, T045, T046, T047 — all Phase 6 quality checks, run in parallel

---

## Implementation Strategy

### MVP (Phase 3 only — US1+US3)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (PDF ingestion + smart table routing)
4. **STOP and VALIDATE**: Ingest the Cooxupé PDF URL, inspect ClickHouse tables, confirm audit columns present, re-ingest to confirm idempotency
5. Demo to stakeholders — data is now queryable

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → PDF ingestion + routing → **MVP demo**
3. Phase 4 → RAG querying → **First CSV export demo**
4. Phase 5 → Web page ingestion → **Full source coverage**
5. Phase 6 → All quality gates pass → **Production ready**

### Parallel Team Strategy

- Developer A: Phase 3 (US1+US3 — ingestion)
- Developer B: Phase 4 (US4 — RAG query)
- Both depend on Phase 2 completing first — coordinate the Phase 2 handoff

---

## Notes

- `[P]` tasks operate on different files with no pending dependencies — safe to run concurrently
- TDD is NON-NEGOTIABLE per Constitution Principle II — never implement before the test is red
- `CREATE_NEW_TABLE_SENTINEL = "__create_new__"` from `constants.py` — use the constant, never the literal string
- Mandatory audit columns (`source_reference`, `ingestion_timestamp`, `content_hash`) are always added by the repository — never let the LLM propose them in `proposed_schema`
- `content_hash` = full 64-character SHA-256 hex digest — no truncation
- Monetary values in ClickHouse: `Decimal(18,4)` — not `Float64`
- All node functions receive dependencies (LLM, repos, clients) via injection — never instantiate `ChatOpenAI` inside a node
- `rag_query_graph` is read-only — any node in that graph that issues a non-SELECT statement is a bug
