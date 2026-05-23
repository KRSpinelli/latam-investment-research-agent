# Contract: RAG Query Graph

**Type**: LangGraph compiled graph (async)
**Module**: `latam_investment_research_agent.agents.analytics.graph.rag_query_graph`
**Graph object**: `rag_query_graph` (instance of `CompiledGraph`)

---

## Invocation

```python
from latam_investment_research_agent.agents.analytics.graph.rag_query_graph import rag_query_graph

result = await rag_query_graph.ainvoke(
    {
        "natural_language_question": "What were Cooxupé's total export revenues by year?",
        "export_row_limit": 10000,
        "export_directory": "./exports",
    }
)
output: RAGQueryOutput = result["rag_query_output"]
```

---

## Input Schema

All fields supplied as a dict to `ainvoke()`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `natural_language_question` | `str` | Yes | — | The question to answer from ClickHouse data |
| `export_row_limit` | `int` | No | `10000` | Maximum rows to include in the CSV export |
| `export_directory` | `str` | No | `"./exports"` | Directory where the CSV file is written |

---

## Output Schema

The graph returns its final state dict. The caller-relevant key is `rag_query_output`.

| Key | Type | Description |
|---|---|---|
| `rag_query_output` | `RAGQueryOutput` | Structured result of the query run |

### RAGQueryOutput fields

| Field | Type | Description |
|---|---|---|
| `export_file_path` | `str` | Absolute path to the written CSV file |
| `rationale` | `str` | Human-readable explanation of why this data answers the question |
| `sql_queries_used` | `list[str]` | The exact SQL queries that were executed |
| `row_count` | `int` | Number of rows in the exported CSV |
| `was_truncated` | `bool` | `True` if results were truncated to `export_row_limit` |

---

## Node Sequence

```
START
  → introspect_schema_node
      Queries ClickHouse system tables to retrieve all user table names
      and their column schemas.
      Sets: available_table_schemas.

  → select_relevant_tables_node
      LLM call (gpt-4o-mini) selects which tables are relevant to the question.
      Sets: selected_table_names.

  → assemble_queries_node
      LLM call generates ClickHouse-compatible SQL for the selected tables.
      All generated queries include LIMIT {export_row_limit}.
      Sets: assembled_sql_queries.

  → execute_queries_node
      Executes all assembled SQL queries against ClickHouse.
      Merges result rows. Truncates to export_row_limit if exceeded.
      Sets: query_result_records, was_truncated.

  → export_results_node
      Uses polars.from_dicts(query_result_records).write_csv(path) to write
      the CSV file. File name: {timestamp}_{question_slug}.csv
      Sets: export_file_path.

  → build_rag_response_node
      Compiles RAGQueryOutput from all accumulated state.
END
```

---

## Error Behaviour

| Condition | Behaviour |
|---|---|
| No tables exist in ClickHouse | `error` set; graph ends without producing a CSV; output explains no data found |
| LLM selects no relevant tables | Output returned with rationale "No relevant data found for this question"; no CSV created |
| SQL query execution fails | Error logged; query skipped; remaining queries attempted; result may be partial |
| ClickHouse connection failure | `error` set; graph ends without producing a CSV |

---

## Read-Only Guarantee

The RAG query graph MUST NOT execute any `INSERT`, `ALTER`, `CREATE`, `DROP`, or `UPDATE`
statements. All assembled SQL queries are validated as `SELECT`-only before execution. Any
query that does not begin with `SELECT` (case-insensitive, after trimming whitespace) is
rejected with an error logged and that query skipped.

---

## CSV File Naming

Export files are named: `{YYYYMMDD_HHMMSS}_{question_slug}.csv`
where `question_slug` is the first 40 characters of the question lowercased with non-alphanumeric
characters replaced by underscores.

Example: `20260523_143012_what_were_cooxupe_s_total_export_reven.csv`

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
