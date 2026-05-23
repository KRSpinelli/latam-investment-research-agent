# Retrieval Layer — Implementation Plan

This module sits **after** the relevance filter and **before** the analysis agent. It implements the architecture split:

| Store | Role | Content |
|-------|------|---------|
| **ClickHouse** | Structured analytics | Metrics, tickers, sentiment scores, signal metadata |
| **Senso.ai** | Semantic memory | Raw documents (HTML, PDF, images) as JSON + metadata |
| **Analysis agent** | Synthesis | Top-N `MarketSignal` objects (future: `EvidencePacket`) |

Upstream: **Nimble** acquires raw documents → **relevance filter** produces **`MarketSignal`**. Downstream stores use dedicated payloads in `schemas/clickhouse.py` and `schemas/senso.py`.

---

## Data flow

```text
List[MarketSignal]  (from relevance filter)
        │
        ▼
   router.route_signal()     ← thresholds in config.py
        │
        ├──► ClickHouseSignalRow + ClickHouseMetricRow  → clickhouse_client (other team)
        ├──► SensoDocumentPayload (raw_content JSON)    → senso_client (other team)
        └──► ranked top-N signals                       → analysis_packet_id
```

---

## Fields by destination

### ClickHouse — `market_signals` table

| Field | Source on `MarketSignal` |
|-------|--------------------------|
| `signal_id` | `signal_id` |
| `document_id` | `document_id` |
| `task_id` | `task_id` |
| `published_at` | `published_at` |
| `crawled_at` | `crawled_at` |
| `country`, `sector`, `subsector` | same |
| `source`, `source_type`, `url` | same |
| `company`, `ticker`, `commodities` | `companies`, `tickers`, `commodities` |
| `signal_type`, `impact`, `sentiment`, `time_horizon` | same |
| `relevance_score`, `confidence`, `summary` | same |

**Route when:** companies, tickers, metrics, or commodities present **and** `relevance_score >= 0.50`, or upstream sets `store_clickhouse=true`.

### ClickHouse — `market_metrics` table (optional MVP+)

One row per `extracted_metrics[]` entry: `metric_name`, `metric_value`, `metric_unit`, `metric_period`, `related_entity`, `related_ticker`, plus signal context (`url`, `sector`, `impact`, etc.).

### Senso — document ingest (JSON handoff)

| Field | Notes |
|-------|--------|
| `raw_content` | `content_type`, `encoding`, `body` — HTML, markdown, or base64 binary |
| `document_id`, `title`, `url` | Traceability |
| `source`, `source_type`, `published_at` | Filtering |
| `country`, `sector`, `companies`, `commodities` | Metadata filters |
| `signal_type`, `summary`, `evidence_snippets` | Retrieval context |
| `nimble_task_id`, `nimble_metadata` | Nimble traceability |
| `relevance_score`, `confidence` | Ranking / quality |

**Route when:** raw document present, filings/reports, or `store_senso=true`, or long `full_text` / high relevance with snippets.

### Analysis agent

Pass **top 5–10** signals ranked by `(relevance_score, confidence, len(extracted_metrics))`. Threshold: both scores **≥ 0.70** unless `send_to_analysis=true`.

Signals below **0.50** relevance: **discard** (raw logs only).

---

## Build order (hackathon)

1. **Done (scaffolding)** — Pydantic models, router, mappers, in-memory clients, `RetrievalAgent.ingest()`, Nimble acquisition.
2. **ClickHouse** — Real `ClickHouseWriter` (other team): `clickhouse-connect`, DDL for `market_signals` + `market_metrics`.
3. **Senso** — Real HTTP/SDK ingest from `SensoDocumentPayload` JSON (other team); env: `SENSO_API_KEY`, workspace/project ids.
4. **LangGraph node** — Wire `RetrievalAgent` after classification node; state holds `list[MarketSignal]`.
5. **EvidencePacket** — Replace raw `analysis_signals` list with compact packet (schema doc §7) when analysis agent is ready.
6. **Observability** — Datadog spans on insert counts, discard reasons, latency.

---

## Env vars (add to `.env` when integrating)

```bash
# Nimble (web acquisition)
NIMBLE_API_KEY=
NIMBLE_BASE_URL=https://sdk.nimbleway.com/v1

# Routing
RETRIEVAL_RELEVANCE_MIN_FOR_ANALYSIS=0.70
RETRIEVAL_CONFIDENCE_MIN_FOR_ANALYSIS=0.70
RETRIEVAL_RELEVANCE_DISCARD_BELOW=0.50
RETRIEVAL_MAX_ANALYSIS_SIGNALS=10

# ClickHouse (step 2)
CLICKHOUSE_HOST=
CLICKHOUSE_USER=
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=latam_alpha

# Senso (step 3)
SENSO_API_KEY=
SENSO_PROJECT_ID=
```

---

## SQL reference (MVP)

```sql
CREATE TABLE market_signals (
    signal_id String,
    document_id String,
    task_id String,
    published_at Nullable(DateTime),
    crawled_at DateTime,
    country String,
    sector String,
    subsector Nullable(String),
    source String,
    source_type String,
    url String,
    company Array(String),
    ticker Array(String),
    commodities Array(String),
    signal_type String,
    impact String,
    sentiment String,
    time_horizon String,
    relevance_score Float32,
    confidence Float32,
    summary String
) ENGINE = MergeTree
ORDER BY (country, sector, crawled_at);
```

---

## Tests

- `tests/agents/retrieval/test_router.py` — routing thresholds and discard
- `tests/agents/retrieval/test_agent.py` — end-to-end ingest with in-memory writers

---

## Module map

```text
agents/retrieval/
  agent.py              # RetrievalAgent.ingest()
  router.py             # route_signal, rank_for_analysis
  mappers.py            # MarketSignal → store payloads
  config.py             # thresholds
  clickhouse_client.py  # Protocol + stub (other team implements)
  senso_client.py       # Protocol + stub (other team implements)
  schemas/
    market_signal.py    # upstream input
    clickhouse.py       # CH rows
    senso.py            # Senso payloads
    routing.py          # RouteDecision, RetrievalOutcome
    enums.py
  PLAN.md               # this file
```
