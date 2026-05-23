"""Shared enums for classification and routing."""

from typing import Literal

SignalType = Literal[
    "export_growth",
    "commodity_price_move",
    "earnings_growth",
    "margin_pressure",
    "capex_expansion",
    "infrastructure_bottleneck",
    "policy_change",
    "regulatory_risk",
    "currency_tailwind",
    "supply_chain_disruption",
    "weather_risk",
    "demand_growth",
    "credit_risk",
    "valuation_signal",
    "management_guidance",
    "other",
]

Impact = Literal["bullish", "bearish", "mixed", "neutral", "unclear"]

Sentiment = Literal["positive", "negative", "neutral", "mixed"]

TimeHorizon = Literal["near_term", "medium_term", "long_term", "unclear"]

# Source types that should prefer Senso (long-form / grounded retrieval).
SENSO_PREFERRED_SOURCE_TYPES = frozenset(
    {
        "filing",
        "filings",
        "earnings_call",
        "pdf",
        "company_report",
        "company_reports",
        "government_data",
        "government_report",
        "policy_document",
        "commodity_report",
        "commodity_reports",
    }
)
