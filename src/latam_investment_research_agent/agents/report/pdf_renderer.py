"""Render analyst report PDFs with reportlab."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from latam_investment_research_agent.agents.report.models import ReportContext, ReportNarrative


def _styles() -> dict[str, ParagraphStyle]:
    """Build paragraph styles for the report.

    Returns:
        Mapping of style name to ParagraphStyle.
    """
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1f4e79"),
            spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "ReportHeading",
            parent=base["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1f4e79"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            leftIndent=18,
            bulletIndent=8,
            spaceAfter=4,
        ),
    }


def _escape_markup(text: str) -> str:
    """Escape characters that break reportlab Paragraph markup.

    Args:
        text: Raw text.

    Returns:
        Safe text for Paragraph.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    """Create a Paragraph with escaped text.

    Args:
        text: Body text.
        style: Reportlab style.

    Returns:
        Formatted paragraph flowable.
    """
    return Paragraph(_escape_markup(text), style)


def _records_table(records: list[dict[str, Any]], max_rows: int = 12) -> Table | Paragraph:
    """Build a simple table from query result records.

    Args:
        records: ClickHouse rows.
        max_rows: Maximum rows to show.

    Returns:
        Table flowable or fallback paragraph.
    """
    if not records:
        return _paragraph("No quantitative data available.", _styles()["body"])

    sample = records[:max_rows]
    columns = list(sample[0].keys())[:6]
    table_data: list[list[str]] = [columns]
    for row in sample:
        table_data.append([str(row.get(column, ""))[:40] for column in columns])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fc")]),
            ]
        )
    )
    return table


def render_report_pdf(context: ReportContext) -> bytes:
    """Render the full analyst report as PDF bytes.

    Args:
        context: Report context including narrative, charts, and data.

    Returns:
        PDF file contents.
    """
    narrative = context.narrative or ReportNarrative(
        executive_summary="Report narrative was not generated.",
        quantitative_analysis="",
        qualitative_analysis="",
        limitations="",
        methodology="",
    )
    style_map = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="LatAm Investment Research Report",
    )

    generated_at = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    story: list[Any] = [
        _paragraph("LatAm Investment Research Agent", style_map["title"]),
        _paragraph(f"<b>Research question:</b> {_escape_markup(context.query)}", style_map["body"]),
        _paragraph(f"<b>Generated:</b> {generated_at}", style_map["body"]),
        Spacer(1, 0.2 * inch),
        _paragraph("Executive Summary", style_map["heading"]),
        _paragraph(narrative.executive_summary, style_map["body"]),
    ]

    if narrative.key_findings:
        story.append(_paragraph("Key Findings", style_map["heading"]))
        for finding in narrative.key_findings:
            story.append(_paragraph(f"• {finding}", style_map["bullet"]))

    story.append(_paragraph("Quantitative Analysis", style_map["heading"]))
    story.append(_paragraph(narrative.quantitative_analysis, style_map["body"]))

    if context.charts:
        story.append(_paragraph("Charts", style_map["heading"]))
        for chart in context.charts:
            story.append(_paragraph(chart.title, style_map["body"]))
            image = Image(str(chart.file_path), width=6.5 * inch, height=3.6 * inch)
            story.append(image)
            story.append(Spacer(1, 0.15 * inch))

    story.append(_paragraph("Data Snapshot", style_map["heading"]))
    story.append(_records_table(context.query_result_records))

    story.append(_paragraph("Qualitative Context", style_map["heading"]))
    story.append(_paragraph(narrative.qualitative_analysis, style_map["body"]))

    story.append(_paragraph("Limitations", style_map["heading"]))
    story.append(_paragraph(narrative.limitations, style_map["body"]))

    story.append(_paragraph("Methodology & Sources", style_map["heading"]))
    story.append(_paragraph(narrative.methodology, style_map["body"]))

    rag = context.rag_output
    sql_lines = rag.get("sql_queries_used", [])
    if sql_lines:
        story.append(_paragraph("SQL queries executed:", style_map["body"]))
        for sql in sql_lines:
            story.append(_paragraph(sql, style_map["bullet"]))

    document.build(story)
    return buffer.getvalue()
