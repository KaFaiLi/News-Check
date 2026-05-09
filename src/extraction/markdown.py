"""HTML → cleaned markdown for LLM consumption.

Strategy: prefer trafilatura's main-content extraction (it strips chrome,
nav, footers, ads). Fall back to html2text on the raw HTML if trafilatura
returns nothing usable. Cap the output length so a single article cannot
blow the LLM context window.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import html2text
import trafilatura


def html_to_markdown(html: str, max_chars: int = 400_000) -> str:
    """Convert article HTML to markdown, capped at `max_chars`."""
    if not html or not html.strip():
        return ""

    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_recall=False,
        no_fallback=False,
    )

    if not extracted or len(extracted.strip()) < 200:
        # Fall back to html2text on the raw HTML.
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        h.skip_internal_links = True
        extracted = h.handle(html)

    md = (extracted or "").strip()
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n[... content truncated for LLM context ...]"
    return md


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def cache_path(cache_dir: Path, url: str) -> Path:
    """Return the on-disk cache path for `url`. Caller is responsible for
    ensuring `cache_dir` exists (use `ensure_cache_dir` once per run)."""
    return Path(cache_dir) / f"{url_hash(url)}.md"


def ensure_cache_dir(cache_dir: Path) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def read_cache(cache_dir: Path, url: str) -> str | None:
    try:
        return cache_path(cache_dir, url).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def write_cache(cache_dir: Path, url: str, markdown: str) -> Path:
    p = cache_path(cache_dir, url)
    p.write_text(markdown, encoding="utf-8")
    return p
