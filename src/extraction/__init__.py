"""Web extraction: Playwright Edge browser, fetcher, markdown conversion."""

from src.extraction.browser import EdgeBrowser
from src.extraction.browser_pool import BrowserPool
from src.extraction.fetcher import PageFetcher, PageResult
from src.extraction.markdown import html_to_markdown
from src.extraction.parallel_fetcher import fetch_and_select

__all__ = [
    "BrowserPool",
    "EdgeBrowser",
    "PageFetcher",
    "PageResult",
    "fetch_and_select",
    "html_to_markdown",
]
