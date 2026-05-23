"""Stub PDF report generation for the research API.

Real report layout and charts will replace this placeholder implementation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime


def _escape_pdf_literal(text: str) -> str:
    """Escape text for use inside a PDF string literal.

    Args:
        text: Raw user-facing text.

    Returns:
        Escaped text safe for PDF content streams.
    """
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _wrap_query_lines(query: str, *, max_line_length: int = 90) -> list[str]:
    """Split a long query into lines for the stub PDF body.

    Args:
        query: Research question text.
        max_line_length: Maximum characters per rendered line.

    Returns:
        Lines to render in the PDF content stream.
    """
    words = query.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_line_length:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [query[:max_line_length]]


def generate_report_pdf(query: str) -> bytes:
    """Build a minimal valid PDF placeholder for a research query.

    Args:
        query: User research question shown on the stub report cover page.

    Returns:
        PDF file bytes suitable for ``Content-Type: application/pdf``.
    """
    generated_at = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    body_lines = [
        "LatAm Investment Research Agent",
        "Research report (stub)",
        f"Generated: {generated_at}",
        "",
        "Query:",
        *_wrap_query_lines(query),
        "",
        "Full PDF report generation is not implemented yet.",
    ]

    text_commands: list[str] = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(body_lines):
        if index > 0:
            text_commands.append("T*")
        text_commands.append(f"({_escape_pdf_literal(line)}) Tj")
    text_commands.append("ET")
    content_stream = " ".join(text_commands) + "\n"
    stream_bytes = content_stream.encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n".encode()
        + stream_bytes
        + b"endstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())

    pdf.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def report_pdf_filename(query: str) -> str:
    """Derive a filesystem-safe PDF filename from the research query.

    Args:
        query: Research question text.

    Returns:
        Filename ending in ``.pdf``.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", query.lower()).strip("-")
    slug = slug[:60] if slug else "research-report"
    return f"{slug}.pdf"
