"""Review a draft analyst PDF and refine narrative plus layout for final render."""

from __future__ import annotations

import io
import logging
import re

import pdfplumber
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from latam_investment_research_agent.agents.report.models import (
    ReportContext,
    ReportFormattingReview,
    ReportNarrative,
    ReportPdfLayoutHints,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an editorial designer for institutional equity research PDFs.

You receive:
1) Structured report sections (draft narrative).
2) Plain text extracted from the draft PDF.

Your job is to clean up formatting and prose for a professional final PDF:
- Fix awkward line breaks, duplicate sentences, and contradictory statements.
- If row_count > 0, never claim quantitative data is missing; cite the data instead.
- Shorten overly long paragraphs; use clear topic sentences.
- Normalize bullet points (no nested markdown, no raw HTML).
- Remove characters that break PDF renderers (< > unescaped, stray markdown headers).
- Keep facts unchanged — do not invent numbers or sources.
- Preserve section structure: executive_summary, key_findings, quantitative_analysis,
  qualitative_analysis, limitations, methodology.

Layout hints:
- Prefer page breaks before charts, data table, and appendix sections.
- Order charts: line, then bar, then pie when all exist.
- Limit SQL appendix to the most important queries (max 8)."""


def extract_text_from_pdf(pdf_bytes: bytes, *, max_characters: int = 24_000) -> str:
    """Extract plain text from a PDF for the review agent.

    Args:
        pdf_bytes: Raw PDF file contents.
        max_characters: Maximum characters to return.

    Returns:
        Concatenated page text or an empty string when extraction fails.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_document:
            page_texts = [
                page.extract_text() or ""
                for page in pdf_document.pages
            ]
        combined = "\n\n".join(text.strip() for text in page_texts if text.strip())
        if len(combined) > max_characters:
            return combined[: max_characters - 3] + "..."
        return combined
    except Exception as error:
        logger.warning("PDF text extraction failed: %s", error)
        return ""


def _sanitize_narrative_text(text: str) -> str:
    """Normalize text for safe reportlab rendering.

    Args:
        text: Raw narrative text.

    Returns:
        Cleaned plain text.
    """
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _build_review_prompt(context: ReportContext, draft_pdf_text: str) -> str:
    """Compose the user message for PDF formatting review.

    Args:
        context: Full report context.
        draft_pdf_text: Text extracted from the draft PDF.

    Returns:
        Prompt string for the LLM.
    """
    narrative = context.narrative or ReportNarrative(
        executive_summary="",
        quantitative_analysis="",
        qualitative_analysis="",
        limitations="",
        methodology="",
    )
    rag = context.rag_output
    chart_types = [chart.chart_type for chart in context.charts]

    return f"""Research question: {context.query}

ClickHouse row_count: {rag.get("row_count", 0)}
Charts present: {", ".join(chart_types) if chart_types else "none"}

Draft narrative (structured):
Executive summary:
{narrative.executive_summary}

Key findings:
{chr(10).join(f"- {item}" for item in narrative.key_findings)}

Quantitative analysis:
{narrative.quantitative_analysis}

Qualitative analysis:
{narrative.qualitative_analysis}

Limitations:
{narrative.limitations}

Methodology:
{narrative.methodology}

Draft PDF plain text (extracted):
{draft_pdf_text or "(extraction empty)"}
"""


async def review_report_formatting(
    context: ReportContext,
    draft_pdf_bytes: bytes,
    language_model: BaseChatModel,
) -> ReportFormattingReview:
    """Review draft PDF text and return cleaned narrative plus layout hints.

    Args:
        context: Report pipeline context including draft narrative.
        draft_pdf_bytes: First-pass PDF bytes.
        language_model: LangChain chat model with structured output.

    Returns:
        Formatting review with copy-edited narrative and layout hints.
    """
    draft_text = extract_text_from_pdf(draft_pdf_bytes)
    structured_language_model = language_model.with_structured_output(ReportFormattingReview)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_build_review_prompt(context, draft_text)),
    ]

    logger.info("Reviewing draft PDF formatting (%d bytes extracted text)", len(draft_text))
    result = await structured_language_model.ainvoke(messages)

    if isinstance(result, ReportFormattingReview):
        review = result
    else:
        review = ReportFormattingReview.model_validate(result)

    review.narrative.executive_summary = _sanitize_narrative_text(
        review.narrative.executive_summary
    )
    review.narrative.quantitative_analysis = _sanitize_narrative_text(
        review.narrative.quantitative_analysis
    )
    review.narrative.qualitative_analysis = _sanitize_narrative_text(
        review.narrative.qualitative_analysis
    )
    review.narrative.limitations = _sanitize_narrative_text(review.narrative.limitations)
    review.narrative.methodology = _sanitize_narrative_text(review.narrative.methodology)
    review.narrative.key_findings = [
        _sanitize_narrative_text(item)
        for item in review.narrative.key_findings
        if _sanitize_narrative_text(item)
    ]

    logger.info(
        "PDF formatting review complete: %s",
        review.formatting_changes_summary or "no summary",
    )
    return review
