"""Discover candidate articles by scraping Google News search.

Google News exposes a date-windowed search via the `tbs=cdr:1,cd_min:..,cd_max:..`
URL parameter and the `tbm=nws` mode. Queries are fanned out across the
shared `BrowserPool` so multiple topic searches run concurrently — each
worker thread owns its own browser context, so identities stay isolated.
"""

from __future__ import annotations

import re
from concurrent.futures import as_completed
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from playwright.sync_api import BrowserContext
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.anti_blocking.session_logger import SessionLogger
from src.extraction.browser_pool import BrowserPool
from src.models import Article, Topic

GOOGLE_NEWS_BASE = "https://www.google.com/search?q={q}&tbm=nws&hl=en-US&gl=us&tbs=cdr:1,cd_min:{lo},cd_max:{hi}"


def _build_query_url(query: str, date_from: date, date_to: date) -> str:
    return GOOGLE_NEWS_BASE.format(
        q=quote_plus(query),
        lo=date_from.strftime("%m/%d/%Y"),
        hi=date_to.strftime("%m/%d/%Y"),
    )


def _resolve_redirect(href: str) -> str | None:
    """Google News result links are sometimes wrapped as `/url?q=ACTUAL`."""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/url?"):
        qs = parse_qs(urlparse(href).query)
        targets = qs.get("q") or qs.get("url")
        if targets:
            return targets[0]
    return None


_RELATIVE_TIME = re.compile(
    r"\b(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago\b", re.IGNORECASE
)
_ABSOLUTE_DATE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b"
)
_YESTERDAY = re.compile(r"\bYesterday\b", re.IGNORECASE)
_TODAY = re.compile(r"\bToday\b", re.IGNORECASE)

# Strip these patterns plus separators/punctuation from titles.
_TITLE_TIME_NOISE = [_RELATIVE_TIME, _ABSOLUTE_DATE, _YESTERDAY, _TODAY]


def _parse_pub_time(text: str | None, *, now: datetime | None = None) -> datetime | None:
    """Find a time marker in `text` and return it as an absolute datetime.

    Recognised formats:
      * Relative: "3 weeks ago", "1 month ago", "5 days ago", "2 hours ago"
      * Absolute: "Apr 5, 2026", "April 5, 2026", "2026-04-05"
      * Special: "Today", "Yesterday"

    Returns `None` if nothing matches. `now` is the reference for relative
    times (defaults to the current wall clock — typically when the
    discovery node ran).
    """
    if not text:
        return None
    now = now or datetime.now()

    m = _RELATIVE_TIME.search(text)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit == "minute":
            return now - timedelta(minutes=n)
        if unit == "hour":
            return now - timedelta(hours=n)
        if unit == "day":
            return now - timedelta(days=n)
        if unit == "week":
            return now - timedelta(weeks=n)
        if unit == "month":
            return now - relativedelta(months=n)
        if unit == "year":
            return now - relativedelta(years=n)

    if _YESTERDAY.search(text):
        return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    if _TODAY.search(text):
        return now.replace(hour=12, minute=0, second=0, microsecond=0)

    abs_m = _ABSOLUTE_DATE.search(text)
    if abs_m:
        candidate = abs_m.group(0).replace(",", "")
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue

    iso_m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso_m:
        try:
            return datetime.strptime(iso_m.group(0), "%Y-%m-%d")
        except ValueError:
            pass

    return None


def _strip_time_from_title(title: str) -> str:
    """Remove relative/absolute time markers from a title and tidy spacing."""
    if not title:
        return ""
    cleaned = title
    for pat in _TITLE_TIME_NOISE:
        cleaned = pat.sub("", cleaned)
    # Collapse separators left behind ("Title ·  · ago" → "Title")
    cleaned = re.sub(r"\s*[·•|]\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;-—")
    return cleaned


def _scrape_query_in_context(
    context: BrowserContext,
    search_url: str,
) -> str:
    """Worker task: navigate to the search URL and return raw HTML."""
    page = context.new_page()
    try:
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeoutError:
            return ""
        page.wait_for_timeout(1_500)  # let the result list settle
        return page.content()
    finally:
        try:
            page.close()
        except Exception:
            pass


class GoogleNewsDiscoverer:
    """Driver for Google News candidate gathering.

    Uses the shared `BrowserPool` so that multiple topic queries run in
    parallel across worker threads. Each worker has its own browser
    context, keeping cookies and UA state isolated per thread.
    """

    def __init__(
        self,
        pool: BrowserPool,
        candidates_per_topic: int,
        logger: SessionLogger | None = None,
    ) -> None:
        self.pool = pool
        self.candidates_per_topic = candidates_per_topic
        self.logger = logger

    def discover(
        self,
        topic: Topic,
        queries: list[str],
        date_from: date,
        date_to: date,
    ) -> list[Article]:
        if not queries:
            return []

        per_query_cap = max(15, self.candidates_per_topic // max(1, len(queries)))
        urls = [_build_query_url(q, date_from, date_to) for q in queries]

        # Submit all query scrapes in parallel.
        future_to_query: dict = {}
        for q, url in zip(queries, urls, strict=False):
            fut = self.pool.submit(_scrape_query_in_context, url)
            future_to_query[fut] = (q, url)

        seen: dict[str, Article] = {}
        for fut in as_completed(future_to_query):
            q, url = future_to_query[fut]
            try:
                html = fut.result()
            except Exception as exc:  # noqa: BLE001
                if self.logger:
                    self.logger.log_failure(url=url, reason=f"discovery error: {exc}")
                continue

            if not html:
                if self.logger:
                    self.logger.log_failure(url=url, reason="empty HTML")
                continue

            cards = parse_google_news_html(html)
            for card in cards[:per_query_cap]:
                if not card.get("url"):
                    continue
                key = card["url"]
                if key in seen:
                    seen[key].appeared_in_topics.add(topic)
                    continue
                article = Article(
                    url=card["url"],
                    title=card.get("title") or "Untitled",
                    source=card.get("source") or "Unknown Source",
                    published_time=card.get("published_time"),
                    snippet=card.get("snippet") or "",
                    discovered_via_topic=topic,
                    discovered_via_query=q,
                    appeared_in_topics={topic},
                )
                seen[key] = article

            if len(seen) >= self.candidates_per_topic:
                break

        return list(seen.values())


# Pulled out as a free function so it can be unit-tested without a browser.
def parse_google_news_html(html: str) -> list[dict]:
    """Parse Google News result cards out of raw HTML.

    Google does not publish a stable DOM for these results; we cast a wide
    net by walking each anchor that points to an external URL and
    collecting nearby text. Intentionally tolerant so small layout changes
    don't break discovery.
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        url = _resolve_redirect(href)
        if not url:
            continue
        if any(s in url for s in ("google.com/", "support.google", "accounts.google")):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Title extraction priority:
        #   1. [role="heading"] descendant — Google's accessible title element
        #   2. <h3>
        #   3. fall back to the anchor text (less reliable, more noisy)
        title_el = a.find(attrs={"role": "heading"}) or a.find("h3")
        if title_el is not None:
            raw_title = title_el.get_text(" ", strip=True)
        else:
            raw_title = a.get_text(" ", strip=True)
        if not raw_title or len(raw_title) < 12:
            continue
        title = _strip_time_from_title(raw_title)
        if len(title) < 8:
            continue

        # Walk up to find a result container with source/snippet/time.
        container = a
        for _ in range(5):
            if container.parent is None:
                break
            container = container.parent
            text = container.get_text(" ", strip=True)
            if len(text) >= len(raw_title) + 30:
                break

        block_text = container.get_text(" ", strip=True)
        published_time = _parse_pub_time(block_text)

        # Snippet: full container text minus the title prefix and time markers.
        snippet = block_text
        if raw_title in snippet:
            snippet = snippet.split(raw_title, 1)[-1].strip()
        for pat in _TITLE_TIME_NOISE:
            snippet = pat.sub("", snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip(" .,;-—·•|")[:400]

        # Source heuristic: text before a separator, with time stripped.
        source = ""
        head = block_text
        if raw_title in head:
            head = head.split(raw_title, 1)[0]
        for pat in _TITLE_TIME_NOISE:
            head = pat.sub("", head)
        head = re.sub(r"\s*[·•|]\s*", " ", head)
        head = re.sub(r"\s+", " ", head).strip(" .,;-—")
        if 2 < len(head) < 60 and head.lower() != title.lower():
            source = head

        results.append(
            {
                "url": url,
                "title": title,
                "source": source or _domain_as_source(url),
                "snippet": snippet,
                "published_time": published_time,
            }
        )

    return results


def _domain_as_source(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")
