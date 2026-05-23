"""Thresholds for the retrieval layer (see agents/retrieval/PLAN.md)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalSettings:
    relevance_min_for_analysis: float = 0.70
    confidence_min_for_analysis: float = 0.70
    relevance_discard_below: float = 0.50
    max_analysis_signals: int = 10


def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings(
        relevance_min_for_analysis=float(
            os.getenv("RETRIEVAL_RELEVANCE_MIN_FOR_ANALYSIS", "0.70")
        ),
        confidence_min_for_analysis=float(
            os.getenv("RETRIEVAL_CONFIDENCE_MIN_FOR_ANALYSIS", "0.70")
        ),
        relevance_discard_below=float(os.getenv("RETRIEVAL_RELEVANCE_DISCARD_BELOW", "0.50")),
        max_analysis_signals=int(os.getenv("RETRIEVAL_MAX_ANALYSIS_SIGNALS", "10")),
    )
