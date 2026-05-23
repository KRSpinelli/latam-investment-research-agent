# Feature Specification: Document Ingestion & RAG Query Agent Framework

**Feature Branch**: `001-document-ingestion-rag`

**Created**: 2026-05-23

**Status**: Draft

**Input**: User description: "Create an agent framework to take pdfs and websites such as the one
here: https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf.
Then find the numerical data within, and upload that to a clickhouse database. For each piece of
data the agent should first try to determine if a relevant table exists, and if so use that table,
otherwise it should create a new table to ingest the data. Every table should include a reference
column with the source of the data for audit purposes. Finally, there should be another final agent
that is used solely for querying the database, a rag agent sitting on top of clickhouse that
assembles relevant queries to gather useful data, then downloads that data to a local csv or other
file format and then provides the path to the file as well as the reason why that data was chosen
and the query used."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ingest a PDF Report (Priority: P1)

A user provides the URL or local file path of a financial PDF report (e.g., an annual co-operative
report published by a LATAM agricultural company). The system fetches or reads the document,
extracts all numerical data along with its surrounding context, routes each dataset to the
appropriate ClickHouse table (creating a new one if no match exists), and confirms successful
ingestion with a summary of what was stored and where.

**Why this priority**: This is the primary ingestion path. All downstream querying and reporting
depends on data being correctly extracted and stored.

**Independent Test**: Provide the Cooxupé 2025 annual report PDF URL. Verify that ClickHouse
contains at least one table with rows sourced from that URL, each row has a non-null reference
column pointing to the source document, and the stored values match figures visible in the PDF.

**Acceptance Scenarios**:

1. **Given** a valid PDF URL, **When** the ingestion agent is invoked, **Then** the document is
   fetched, numerical data is extracted with context labels, and at least one ClickHouse table
   contains the extracted rows with a populated `source_reference` column.
2. **Given** the same PDF URL is ingested a second time, **When** the ingestion agent runs again,
   **Then** duplicate rows are not inserted (idempotency is maintained via source reference
   deduplication).
3. **Given** a PDF with no numerical content, **When** the ingestion agent runs, **Then** the
   system reports zero rows ingested and no tables are created or modified.

---

### User Story 2 — Ingest a Web Page (Priority: P2)

A user provides the URL of a public web page containing financial or statistical tables (e.g., a
commodity price page, a government statistics portal). The system fetches the page, extracts
numerical data, and stores it in ClickHouse using the same table-routing and reference-column
logic as PDF ingestion.

**Why this priority**: Web pages are an equally important source of LATAM financial data; the
ingestion pipeline MUST be source-agnostic from the user's perspective.

**Independent Test**: Provide a public financial statistics web page URL. Verify rows appear in
ClickHouse with the correct `source_reference` URL and that extracted numbers match values visible
on the page.

**Acceptance Scenarios**:

1. **Given** a valid public web page URL with numerical tables, **When** the ingestion agent is
   invoked, **Then** extracted numerical data is stored in ClickHouse with the page URL as the
   source reference.
2. **Given** a web page that requires JavaScript rendering to display data, **When** the ingestion
   agent processes it, **Then** the system falls back gracefully and reports which data could not
   be extracted, without crashing.

---

### User Story 3 — Smart Table Routing (Priority: P1)

When the ingestion agent extracts a dataset (e.g., "annual coffee production volumes by region"),
it queries the ClickHouse schema to determine whether a semantically compatible table already
exists. If a match is found, new rows are appended; if not, a new table is created with an
appropriate schema derived from the data's structure and context labels.

**Why this priority**: Correct table routing prevents data fragmentation and ensures downstream
queries can join related datasets. It is architecturally foundational.

**Independent Test**: Ingest two different PDFs that both contain "annual revenue" data. Verify
that the rows from both documents land in the same ClickHouse table (not two separate tables),
and that both rows have distinct `source_reference` values.

**Acceptance Scenarios**:

1. **Given** extracted data whose semantic category matches an existing ClickHouse table, **When**
   the routing agent evaluates the schema, **Then** rows are inserted into the existing table
   without schema modification.
2. **Given** extracted data whose semantic category has no existing ClickHouse table, **When** the
   routing agent evaluates the schema, **Then** a new table is created with columns derived from
   the dataset's structure, including a `source_reference` column.
3. **Given** a newly created table receives a second dataset from a different source with the same
   semantic category, **When** the routing agent evaluates the schema, **Then** it correctly
   identifies the existing table and appends rather than creating a duplicate.

---

### User Story 4 — RAG Query Agent: Data Retrieval & Export (Priority: P1)

A user asks a natural-language question about LATAM financial data (e.g., "What was Cooxupé's
total revenue trend over the last three years?"). The RAG query agent interprets the question,
assembles one or more ClickHouse SQL queries to retrieve the most relevant data, executes the
queries, exports the results to a local CSV file, and responds with the file path, the rationale
for why this data answers the question, and the exact SQL query used.

**Why this priority**: This is the primary output interface. A future reporting project depends on
this agent producing structured, queryable exports.

**Independent Test**: Ask the RAG agent "What are the total export volumes by year from Cooxupé?"
after ingesting the Cooxupé PDF. Verify that a CSV file is created at the reported path, the file
contains year and volume columns, and the provided SQL query is valid and reproducible.

**Acceptance Scenarios**:

1. **Given** relevant data exists in ClickHouse, **When** the RAG query agent receives a
   natural-language question, **Then** it returns a local file path to a CSV export, a
   human-readable rationale explaining why the data answers the question, and the SQL query used.
2. **Given** the RAG query agent assembles a query, **When** the query is executed, **Then** the
   exported file contains only the rows directly relevant to the question (not the entire table).
3. **Given** no relevant data exists in ClickHouse for the question, **When** the RAG query agent
   runs, **Then** it responds that no matching data was found and does not produce an empty file.
4. **Given** the RAG agent uses multiple tables to answer a question, **When** the query is built,
   **Then** the exported CSV and the returned SQL reflect the join or union logic used.

---

### Edge Cases

- What happens when the PDF is password-protected or corrupted?
  → System reports the error with document details; no partial data is stored.
- What happens when a web page returns a non-200 HTTP status or is behind authentication?
  → System reports the inaccessible URL; ingestion is skipped for that source.
- What happens when extracted numbers are ambiguous (e.g., "1,234" could be 1.234 or 1234 depending on locale)?
  → System applies locale-aware parsing based on document language/region metadata; ambiguous values are flagged in an `extraction_notes` column.
- What happens when ClickHouse is unreachable during ingestion?
  → System halts ingestion, reports the connection failure, and does not partially commit data.
- What happens when a ClickHouse write fails after some datasets have already been committed?
  → Previously committed rows are retained (no rollback); the agent logs the failure with the
  failed dataset's identity and error detail, continues attempting remaining datasets, and
  returns a structured ingestion summary listing which datasets succeeded and which failed.
- What happens when the RAG agent generates a SQL query that returns more than the row limit?
  → The export is truncated to 10,000 rows (default, caller-configurable), the truncation is
  noted in the rationale output, and the full SQL query is still returned.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion agent MUST accept as input either a URL (pointing to a PDF or web
  page) or a local file path to a PDF document.
- **FR-002**: The ingestion agent MUST extract all numerical data from the source document along
  with contextual labels (e.g., row/column headers, surrounding text) sufficient to categorize
  the data semantically.
- **FR-003**: For each extracted dataset, the ingestion agent MUST retrieve existing ClickHouse
  table names and their column schemas, then invoke an LLM-based routing node that returns
  either the name of a compatible existing table or an instruction to create a new table;
  this decision MUST be made before writing any data.
- **FR-004**: If a compatible table exists, the ingestion agent MUST append new rows to that
  table without altering its schema (unless the new data introduces additional columns, in which
  case schema migration MUST be applied).
- **FR-005**: If no compatible table exists, the ingestion agent MUST create a new ClickHouse
  table with a schema derived from the extracted dataset's structure.
- **FR-006**: Every row inserted into any ClickHouse table MUST include a `source_reference`
  column containing the URL or file path of the originating document, and an
  `ingestion_timestamp` column recording when the row was inserted.
- **FR-007**: The ingestion agent MUST be idempotent: re-ingesting the same source document MUST
  NOT produce duplicate rows (deduplication keyed on `source_reference` + row-level content hash).
- **FR-008**: The RAG query agent MUST accept a natural-language question as input and MUST NOT
  accept raw SQL as input.
- **FR-009**: The RAG query agent MUST assemble and execute one or more ClickHouse SQL queries
  to retrieve data relevant to the question.
- **FR-010**: The RAG query agent MUST export query results to a local file (CSV as default
  format; other formats are out of scope for v1).
- **FR-011**: The RAG query agent MUST return, in its response: (a) the absolute path to the
  exported file, (b) a human-readable rationale explaining why the retrieved data is relevant to
  the question, and (c) the exact SQL query or queries used.
- **FR-012**: The RAG query agent MUST be implemented as a separate compiled LangGraph graph —
  it MUST NOT share runtime state with the ingestion agent graph, and MUST be independently
  invocable by the parent orchestrator.
- **FR-013**: Both agents MUST log all operations (ingestion events, table routing decisions,
  query construction, export events) with structured log entries.
- **FR-014**: Upon completion of an ingestion run (whether fully successful or partially failed),
  the ingestion agent MUST return a structured ingestion summary listing each extracted dataset,
  its routing decision (table name used or created), write success or failure status, and any
  error detail for failed datasets.
- **FR-015**: All ClickHouse connection settings (host, port, database, username, password) MUST
  be supplied exclusively via environment variables. A `.env.sample` file documenting every
  required variable with placeholder values MUST be included in the repository.
- **FR-016**: The RAG query agent MUST apply a default maximum row limit of 10,000 rows to all
  CSV exports. The caller MAY override this limit. When the limit is reached, the truncation
  MUST be noted in the rationale output returned alongside the file path.

### Key Entities

- **Source Document**: A PDF file or web page URL submitted for ingestion; identified by its URL
  or file path.
- **Extracted Dataset**: A named collection of numerical values with contextual labels, extracted
  from one section of a source document (e.g., "Annual Revenue by Year", "Coffee Export Volumes
  by Region").
- **ClickHouse Table**: A columnar table storing one category of financial/statistical data;
  always includes `source_reference` and `ingestion_timestamp` audit columns.
- **Table Routing Decision**: The agent's determination of whether an extracted dataset maps to
  an existing table or requires a new one; recorded in the structured log.
- **Query Result Export**: A local CSV file produced by the RAG query agent, keyed by a
  session/query identifier and timestamped.
- **RAG Response**: The structured output of the RAG query agent: file path + rationale +
  SQL used.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A financial PDF of up to 100 pages is fully ingested (extraction + ClickHouse
  writes complete) within 5 minutes on standard hardware.
- **SC-002**: At least 95% of numerical values visible in a source document are captured in the
  ClickHouse output (measured against a manually verified ground-truth sample).
- **SC-003**: When the same source document is ingested twice, zero duplicate rows appear in
  ClickHouse (100% idempotency rate).
- **SC-004**: The RAG query agent returns a valid CSV export and rationale within 30 seconds of
  receiving a natural-language question, for questions answerable from up to 10 ClickHouse tables.
- **SC-005**: 90% of natural-language questions about ingested data produce a CSV export
  containing at least one row directly relevant to the question, as judged by a human reviewer.
- **SC-006**: Every row in every ClickHouse table has a non-null `source_reference` value (100%
  audit coverage).
- **SC-007**: The system correctly routes datasets to an existing table (rather than creating a
  duplicate) at least 90% of the time when a semantically compatible table exists, measured over
  a test corpus of 20 documents covering overlapping financial categories.

---

## Clarifications

### Session 2026-05-23

- Q: How are the ingestion and RAG query agents invoked? → A: LangGraph-native — both agents are compiled LangGraph graph objects invoked programmatically by the parent LATAM investment research agent orchestrator; no CLI or HTTP server interface.
- Q: How does the ingestion agent determine semantic compatibility between an extracted dataset and an existing ClickHouse table? → A: LLM judgment — the routing node passes the extracted dataset's context labels and structure alongside retrieved existing table names and column schemas to an LLM call; the LLM returns the target table name or "create new".
- Q: If ingestion partially fails mid-document (some datasets written, then an error), what happens to already-committed rows? → A: Commit partial — rows already written are retained; each failure is logged with dataset identity and error detail; the agent returns a structured ingestion summary listing succeeded and failed datasets.
- Q: How are ClickHouse connection credentials and settings supplied to the agents? → A: Environment variables; a `.env.sample` file documenting all required variables MUST be provided in the repository.
- Q: What is the default maximum row limit for CSV exports from the RAG query agent? → A: 10,000 rows (configurable by the caller; truncation noted in the rationale output when limit is reached).

## Assumptions

- Source documents are publicly accessible (no authentication required for URLs); authenticated
  sources are out of scope for v1.
- PDF documents are text-based (digitally created); scanned image-only PDFs requiring OCR are
  out of scope for v1 but the architecture MUST not preclude adding OCR in a future version.
- The ClickHouse instance is pre-provisioned and network-accessible; the agents do not manage
  ClickHouse infrastructure.
- ClickHouse connection credentials are provided via environment variables; a `.env.sample`
  file documents the required variables (e.g., `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`,
  `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`).
- The operating environment has sufficient disk space for CSV exports; export file cleanup is
  out of scope.
- The RAG query agent operates in a read-only mode against ClickHouse; it MUST NOT insert,
  update, or delete rows.
- "Numerical data" means quantitative values (integers, decimals, percentages, monetary amounts,
  volumes) along with their contextual labels — not free-text narrative paragraphs.
- The primary document domain is LATAM financial and agricultural reports; the system is
  general-purpose but optimized for this domain's data structures (tabular financial statements,
  production statistics, pricing data).
- A single ingestion run processes one source document at a time; batch ingestion of multiple
  documents is out of scope for v1.
- Both agents are LangGraph graph objects; neither exposes a CLI command or HTTP endpoint
  directly — invocation is handled entirely by the parent orchestrator.
