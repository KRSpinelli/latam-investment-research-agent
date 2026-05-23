# LatAm Investment Research Agent

An investment research agent for emerging markets in Latin America.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
# Add your Nimble API key to .env
```

## Run API (frontend entry point)

```bash
uv run latam-api
# or
uv run uvicorn latam_investment_research_agent.api.app:app --reload --host 0.0.0.0 --port 8000
```

Open interactive docs: http://localhost:8000/docs

### Example research request

```bash
curl -X POST http://localhost:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Identify underfollowed Brazilian companies benefiting from soybean export growth",
    "seed_urls": [
      "https://www.infomoney.com.br/business/cooxupe-se-prepara-para-receber-7-milhoes-de-sacas-de-cafe-em-2024/",
      "https://www.cooxupe.com.br/wp-content/uploads/2026/04/ENG_relatorio-web_revisado_completo_compressed.pdf"
    ],
    "max_documents": 8
  }'
```

Demo queries and seed URLs: `GET /api/v1/research/examples`

### Pipeline

```text
POST /api/v1/research
  → Nimble (web search + scrape: HTML, PDF, wiki, images, …)
  → Relevance filter → MarketSignal[]
  → Retrieval agent → ClickHouse (structured fields) / Senso (raw JSON) / analysis packet
```

Set `NIMBLE_API_KEY` in `.env` before running against live web data.

## Retrieval demo (no HTTP)

```bash
uv run python scripts/demo_retrieval.py
```

## Test

```bash
uv run pytest
```

## Lint and format

```bash
uv run ruff check .
uv run ruff format .
```

## Type check

```bash
uv run mypy src
```

## Integration boundaries

| Component | Owner | Contract |
|-----------|-------|----------|
| Nimble acquisition | This repo | `NimbleDocument` → `MarketSignal` |
| ClickHouse writes | Other team | `ClickHouseWriter` protocol + row schemas |
| Senso ingest | Other team | `SensoDocumentPayload` JSON with `raw_content` |
