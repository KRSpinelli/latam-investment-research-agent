"""Tests for Senso document URL fetching."""

from __future__ import annotations

from latam_investment_research_agent.agents.semantic_storage.document_fetch import (
    _extract_full_page_text_from_html_bytes,
)


def test_extract_full_page_text_from_html_includes_article_body() -> None:
    html = b"""
    <html>
      <head><title>Ignored</title><style>.x{}</style></head>
      <body>
        <nav>Menu item</nav>
        <article>
          <h1>Coffee outlook</h1>
          <p>Exports rose 7.7 percent in 2024.</p>
        </article>
        <footer>Copyright</footer>
      </body>
    </html>
    """
    text = _extract_full_page_text_from_html_bytes(html)

    assert "Coffee outlook" in text
    assert "Exports rose 7.7 percent" in text
    assert "Menu item" not in text
    assert "Copyright" not in text
