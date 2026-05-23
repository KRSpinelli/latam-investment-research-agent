"""Relevance filter — turns Nimble documents into MarketSignal objects (MVP heuristics)."""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse

from latam_investment_research_agent.agents.nimble.schemas import NimbleDocument
from latam_investment_research_agent.agents.retrieval.schemas.enums import SignalType
from latam_investment_research_agent.agents.retrieval.schemas.market_signal import MarketSignal

_TICKER_RE = re.compile(r"\b([A-Z]{4}\d{1,2})\b")
_COMMODITY_KEYWORDS: dict[str, str] = {
    "soybean": "Soybeans",
    "soja": "Soybeans",
    "coffee": "Coffee",
    "cafe": "Coffee",
    "café": "Coffee",
    "corn": "Corn",
    "milho": "Corn",
    "sugar": "Sugar",
    "açúcar": "Sugar",
    "iron ore": "Iron ore",
    "minério": "Iron ore",
}

_SIGNAL_TYPE_RULES: list[tuple[tuple[str, ...], SignalType]] = [
    (("infrastructure", "logistics", "port", "rail", "ferrovia"), "infrastructure_bottleneck"),
    (("export", "exportação", "exportacao"), "export_growth"),
    (("capex", "investment", "investimento"), "capex_expansion"),
    (("earnings", "lucro", "receita", "revenue"), "earnings_growth"),
]


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", text)}


def _score_relevance(query: str, doc: NimbleDocument) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.5
    doc_tokens = _tokenize(f"{doc.title} {doc.text}")
    if not doc_tokens:
        return 0.2
    overlap = len(query_tokens & doc_tokens) / len(query_tokens)
    base = 0.45 + overlap * 0.5
    if doc.source_type in {"company_report", "company_reports"}:
        base += 0.05
    return min(0.98, base)


def _score_confidence(doc: NimbleDocument) -> float:
    length = len(doc.text)
    if length > 5000:
        return 0.88
    if length > 1500:
        return 0.78
    if length > 400:
        return 0.72
    return 0.55


def _infer_signal_type(query: str, text: str) -> SignalType:
    blob = f"{query} {text}".lower()
    for keywords, signal_type in _SIGNAL_TYPE_RULES:
        if any(k in blob for k in keywords):
            return signal_type
    return "other"


def _infer_commodities(query: str, text: str) -> list[str]:
    blob = f"{query} {text}".lower()
    found: list[str] = []
    for key, label in _COMMODITY_KEYWORDS.items():
        if key in blob and label not in found:
            found.append(label)
    return found


def _infer_companies(doc: NimbleDocument) -> list[str]:
    host = urlparse(doc.final_url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    label = host.split(".")[0]
    if label and label not in {"infomoney", "reuters", "bloomberg", "example"}:
        return [label.replace("-", " ").title()]
    tickers = _TICKER_RE.findall(doc.text)
    if tickers:
        return []
    return []


def _evidence_snippets(query: str, text: str, limit: int = 3) -> list[str]:
    tokens = _tokenize(query)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        lower = sentence.lower()
        hits = sum(1 for t in tokens if t in lower)
        if hits:
            scored.append((hits, sentence.strip()[:500]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:limit]]


def _document_id(url: str) -> str:
    return f"doc_{uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:12]}"


class RelevanceFilterAgent:
    """MVP classifier — keyword overlap and source-type heuristics."""

    def classify(
        self,
        query: str,
        documents: list[NimbleDocument],
        *,
        task_id: str,
    ) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        for doc in documents:
            if not doc.ok:
                continue
            signal_id = f"sig_{uuid.uuid5(uuid.NAMESPACE_URL, doc.final_url).hex[:12]}"
            commodities = _infer_commodities(query, doc.text)
            tickers = list(dict.fromkeys(_TICKER_RE.findall(doc.text)))[:8]
            companies = _infer_companies(doc)
            summary = doc.text[:600].strip() or doc.title
            signals.append(
                MarketSignal(
                    signal_id=signal_id,
                    task_id=task_id,
                    document_id=_document_id(doc.final_url),
                    title=doc.title[:300],
                    url=doc.final_url,
                    source=urlparse(doc.final_url).netloc,
                    source_type=doc.source_type,
                    crawled_at=doc.fetched_at,
                    sector="Agriculture" if commodities else "General",
                    summary=summary,
                    evidence_snippets=_evidence_snippets(query, doc.text),
                    companies=companies,
                    tickers=tickers,
                    commodities=commodities,
                    signal_type=_infer_signal_type(query, doc.text),
                    impact="unclear",
                    sentiment="neutral",
                    relevance_score=_score_relevance(query, doc),
                    confidence=_score_confidence(doc),
                    full_text=doc.text[:50_000] if len(doc.text) > 500 else None,
                    raw_content_type=doc.content_type,
                    raw_content_body=doc.raw_body,
                    raw_content_encoding=doc.raw_encoding,
                    nimble_task_id=doc.nimble_task_id,
                    nimble_metadata=dict(doc.metadata),
                    store_senso=doc.source_type in {"company_report", "company_reports"},
                )
            )
        return signals
