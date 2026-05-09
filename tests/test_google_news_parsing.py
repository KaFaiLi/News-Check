"""Tests for Google News result parsing — title/time stripping and date parsing.

The HTML fixtures here are simplified facsimiles of how Google News result
cards have been observed to look — Google does not publish a stable schema,
so the parser needs to be tolerant. We intentionally include the failure
modes that motivated the fix: relative-time strings concatenated into the
title, and missing / never-extracted `published_time`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from src.discovery.google_news import (
    _parse_pub_time,
    _strip_time_from_title,
    parse_google_news_html,
)

# ---------- _strip_time_from_title ----------


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("OpenAI launches new model 3 weeks ago", "OpenAI launches new model"),
        ("Some headline 1 month ago", "Some headline"),
        ("Big story · Yesterday", "Big story"),
        ("Today: AI breakthrough", ": AI breakthrough"),  # noisy but de-noised
        ("Major deal · Apr 5, 2026", "Major deal"),
        ("Headline with no time markers at all", "Headline with no time markers at all"),
    ],
)
def test_strip_time_from_title(raw, clean):
    assert _strip_time_from_title(raw) == clean


# ---------- _parse_pub_time ----------


def test_parse_relative_weeks():
    now = datetime(2026, 5, 9, 12, 0, 0)
    out = _parse_pub_time("3 weeks ago", now=now)
    assert out is not None
    assert out == now - timedelta(weeks=3)


def test_parse_relative_months():
    now = datetime(2026, 5, 9, 12, 0, 0)
    out = _parse_pub_time("1 month ago", now=now)
    assert out == now - relativedelta(months=1)


def test_parse_relative_days():
    now = datetime(2026, 5, 9, 12, 0, 0)
    out = _parse_pub_time("5 days ago", now=now)
    assert out == now - timedelta(days=5)


def test_parse_relative_hours():
    now = datetime(2026, 5, 9, 12, 0, 0)
    out = _parse_pub_time("2 hours ago", now=now)
    assert out == now - timedelta(hours=2)


def test_parse_yesterday():
    now = datetime(2026, 5, 9, 12, 0, 0)
    out = _parse_pub_time("Yesterday", now=now)
    assert out is not None
    assert out.date() == (now - timedelta(days=1)).date()


def test_parse_absolute_short_month():
    out = _parse_pub_time("Apr 5, 2026")
    assert out == datetime(2026, 4, 5)


def test_parse_absolute_long_month():
    out = _parse_pub_time("April 22, 2026")
    assert out == datetime(2026, 4, 22)


def test_parse_iso_date():
    out = _parse_pub_time("2026-04-05")
    assert out == datetime(2026, 4, 5)


def test_parse_returns_none_for_no_marker():
    assert _parse_pub_time("Just a headline with no date in it") is None


def test_parse_returns_none_for_empty():
    assert _parse_pub_time("") is None
    assert _parse_pub_time(None) is None


# ---------- parse_google_news_html (end-to-end) ----------


def _build_card(*, title: str, source: str, time_text: str, snippet: str, url: str) -> str:
    return f"""
    <div class="g">
      <a href="/url?q={url}&amp;source=newssearch">
        <div role="heading" aria-level="3">{title}</div>
      </a>
      <div>
        <div>{source}</div>
        <div>{snippet}</div>
        <div>{time_text}</div>
      </div>
    </div>
    """


def test_parser_uses_role_heading_for_title():
    html = f"<html><body>{_build_card(title='OpenAI raises $40B', source='Bloomberg', time_text='3 weeks ago', snippet='Story body...', url='https://bloomberg.com/openai-raise')}</body></html>"
    cards = parse_google_news_html(html)
    assert len(cards) >= 1
    card = cards[0]
    assert card["title"] == "OpenAI raises $40B"
    assert "3 weeks ago" not in card["title"]


def test_parser_extracts_relative_pub_time():
    html = f"<html><body>{_build_card(title='Bank deal of the year', source='FT', time_text='2 weeks ago', snippet='Snippet text', url='https://ft.com/bank-deal')}</body></html>"
    cards = parse_google_news_html(html)
    assert cards
    pub = cards[0]["published_time"]
    assert isinstance(pub, datetime)
    # Should be ~14 days before now
    delta = datetime.now() - pub
    assert 13 <= delta.days <= 15


def test_parser_strips_time_when_in_anchor_text_fallback():
    """When there's no role=heading, the parser falls back to anchor text.
    Time markers must still be stripped."""
    html = """
    <html><body>
      <div>
        <a href="/url?q=https://reuters.com/x">
          AI agents in finance 1 month ago
        </a>
        <div>Reuters · Snippet text here</div>
      </div>
    </body></html>
    """
    cards = parse_google_news_html(html)
    assert cards
    assert "1 month ago" not in cards[0]["title"]
    assert "AI agents in finance" in cards[0]["title"]


def test_parser_returns_none_pub_time_when_card_has_no_time():
    html = """
    <html><body>
      <div>
        <a href="/url?q=https://example.com/x">
          <div role="heading">Headline with no time text</div>
        </a>
        <div>Just a source name</div>
      </div>
    </body></html>
    """
    cards = parse_google_news_html(html)
    assert cards
    assert cards[0]["published_time"] is None


def test_parser_skips_google_internal_links():
    html = """
    <html><body>
      <a href="/search?q=more">More results</a>
      <a href="https://support.google.com/help">Help</a>
      <a href="/url?q=https://realsite.com/article"><div role="heading">Real article title here</div></a>
    </body></html>
    """
    cards = parse_google_news_html(html)
    urls = [c["url"] for c in cards]
    assert all("google.com" not in u for u in urls)
    assert "https://realsite.com/article" in urls
