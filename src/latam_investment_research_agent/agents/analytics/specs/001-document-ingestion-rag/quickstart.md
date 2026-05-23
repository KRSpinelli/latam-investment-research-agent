# Quickstart: Document Ingestion & RAG Query Agent Framework

**Branch**: `001-document-ingestion-rag` | **Date**: 2026-05-23

---

## Prerequisites

- Python 3.12+
- A running ClickHouse instance (local or remote)
- An OpenAI API key

---

## 1. Install Dependencies

```bash
# From the analytics agent directory
pip install -e ".[dev]"
# Or with uv:
uv sync
```

Key packages installed:
- `langgraph` — agent graph orchestration
- `langchain-openai` — OpenAI LLM provider
- `langchain-core` — LLM provider abstraction
- `clickhouse-connect` — ClickHouse Python driver
- `pdfplumber` — PDF table extraction
- `httpx` — async HTTP client
- `beautifulsoup4` — HTML table parsing
- `polars` — CSV export
- `pydantic` — data validation

---

## 2. Configure Environment

Copy the sample environment file and fill in your values:

```bash
cp .env.sample .env
```

Edit `.env`:

```
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8443
CLICKHOUSE_DATABASE=latam_research
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_password_here

OPENAI_API_KEY=sk-...

# Optional: change LLM provider or model
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4o-mini
```

---

## 3. Ingest a Document

```python
import asyncio
from latam_investment_research_agent.agents.analytics.graph.ingestion_graph import ingestion_graph

async def main():
    result = await ingestion_graph.ainvoke({
        "source_reference": "https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf"
    })
    summary = result["ingestion_summary"]
    print(f"Datasets found: {summary.total_datasets_found}")
    print(f"Succeeded: {len(summary.datasets_succeeded)}")
    print(f"Failed: {len(summary.datasets_failed)}")
    for dataset_result in summary.datasets_succeeded:
        print(f"  → {dataset_result.dataset_name} → {dataset_result.target_table_name} ({dataset_result.rows_written} rows)")

asyncio.run(main())
```

---

## 4. Query the Database

```python
import asyncio
from latam_investment_research_agent.agents.analytics.graph.rag_query_graph import rag_query_graph

async def main():
    result = await rag_query_graph.ainvoke({
        "natural_language_question": "What were Cooxupé's total export revenues by year?",
        "export_row_limit": 10000,
        "export_directory": "./exports",
    })
    output = result["rag_query_output"]
    print(f"CSV exported to: {output.export_file_path}")
    print(f"Rows: {output.row_count} (truncated: {output.was_truncated})")
    print(f"\nRationale:\n{output.rationale}")
    print(f"\nSQL used:")
    for sql_query in output.sql_queries_used:
        print(sql_query)

asyncio.run(main())
```

---

## 5. Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=latam_investment_research_agent.agents.analytics --cov-report=term-missing

# Unit tests only
pytest tests/unit/

# Integration tests (requires live ClickHouse)
pytest tests/integration/

# Performance benchmarks
pytest tests/performance/
```

---

## 6. Validate Your Installation

After running a successful ingestion, verify data in ClickHouse:

```python
import clickhouse_connect
from latam_investment_research_agent.agents.analytics.config import AnalyticsConfig

config = AnalyticsConfig()
client = clickhouse_connect.get_client(
    host=config.clickhouse_host,
    port=config.clickhouse_port,
    database=config.clickhouse_database,
    username=config.clickhouse_user,
    password=config.clickhouse_password,
)

# List all ingested tables
tables = client.query("SHOW TABLES").result_rows
print("Tables:", tables)

# Check audit columns exist on first table
if tables:
    table_name = tables[0][0]
    sample = client.query(
        f"SELECT source_reference, ingestion_timestamp, content_hash FROM {table_name} LIMIT 5"
    ).result_rows
    for row in sample:
        print(row)
```

---

## 7. Swap LLM Provider

To switch from OpenAI to Anthropic (no code changes required):

```bash
# .env
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-3-5-haiku-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

Install the Anthropic integration:

```bash
pip install langchain-anthropic
```

The `create_llm_provider()` factory in `providers/llm_provider.py` reads `LLM_PROVIDER` and
returns the appropriate `BaseChatModel` automatically.
