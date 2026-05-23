# Contract: Ingestion Graph

**Type**: LangGraph compiled graph (async)
**Module**: `latam_investment_research_agent.agents.analytics.graph.ingestion_graph`
**Graph object**: `ingestion_graph` (instance of `CompiledGraph`)

---

## Invocation

```python
from latam_investment_research_agent.agents.analytics.graph.ingestion_graph import ingestion_graph

result = await ingestion_graph.ainvoke(
    {
        "source_reference": "https://example.com/report.pdf",
    }
)
summary: IngestionSummary = result["ingestion_summary"]
```

---

## Input Schema

All fields supplied as a dict to `ainvoke()`.

| Field | Type | Required | Description |
|---|---|---|---|
| `source_reference` | `str` | Yes | URL (PDF or static web page) or absolute local file path |

---

## Output Schema

The graph returns its final state dict. The caller-relevant key is `ingestion_summary`.

| Key | Type | Description |
|---|---|---|
| `ingestion_summary` | `IngestionSummary` | Structured result of the ingestion run |

### IngestionSummary fields

| Field | Type | Description |
|---|---|---|
| `source_reference` | `str` | The source that was processed |
| `total_datasets_found` | `int` | Number of numerical datasets identified in the document |
| `datasets_succeeded` | `list[DatasetIngestionResult]` | Datasets written to ClickHouse |
| `datasets_failed` | `list[DatasetIngestionFailure]` | Datasets that could not be written |

---

## Node Sequence

```
START
  → fetch_document_node
      Fetches raw content from URL (PDF or HTML) or reads local file.
      Sets: raw_content, or error on fatal failure.

  → extract_numerical_data_node
      LLM call (gpt-4o-mini) extracts structured datasets from raw_content.
      Sets: extracted_datasets.

  → persist_datasets_node
      Introspects ClickHouse schema once, routes all datasets in parallel,
      applies create/alter DDL in parallel, and bulk-inserts rows in parallel.
      Appends to ingestion_results or ingestion_failures per dataset.

  → build_ingestion_summary_node
      Compiles IngestionSummary from ingestion_results and ingestion_failures.
END
```

---

## Error Behaviour

| Condition | Behaviour |
|---|---|
| Document fetch fails (network error, 4xx/5xx, corrupt PDF) | `error` set in state; graph routes to `build_ingestion_summary_node` with zero datasets |
| LLM extraction returns zero datasets | `total_datasets_found = 0`; summary returned normally; no error |
| Individual dataset write fails | Appended to `datasets_failed`; processing continues with remaining datasets |
| ClickHouse connection failure | Dataset write fails; appended to `datasets_failed`; remaining datasets attempted |

---

## Idempotency

Re-invoking with the same `source_reference` on a document already ingested produces zero
new rows. Deduplication key: `(source_reference, content_hash)` per row.

---

## Required Environment Variables

| Variable | Description |
|---|---|
| `CLICKHOUSE_HOST` | ClickHouse server hostname |
| `CLICKHOUSE_PORT` | ClickHouse HTTP port (default 8443) |
| `CLICKHOUSE_DATABASE` | Target database name |
| `CLICKHOUSE_USER` | ClickHouse username |
| `CLICKHOUSE_PASSWORD` | ClickHouse password |
| `OPENAI_API_KEY` | OpenAI API key (default LLM provider) |
| `LLM_PROVIDER` | Optional override (default `openai`) |
| `LLM_MODEL_NAME` | Optional override (default `gpt-4o-mini`) |
