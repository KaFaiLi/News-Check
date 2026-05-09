"""Page fetcher: URL → rendered HTML, with anti-block retry wrapping."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.anti_blocking.block_detector import (
    BlockClassification,
    BlockType,
    classify_response,
    classify_status,
)
from src.anti_blocking.retry_policy import (
    AttemptResult,
    RetryConfig,
    RetryExhausted,
    run_with_retry,
)
from src.anti_blocking.session_logger import SessionLogger
from src.extraction.browser import EdgeBrowser


@dataclass
class PageResult:
    url: str
    final_url: str
    status: int | None
    html: str


class PageFetcher:
    """Fetches a fully-rendered page using a shared `EdgeBrowser`.

    `fetch` returns the HTML of the final document or raises `RetryExhausted`.
    """

    def __init__(
        self,
        browser: EdgeBrowser,
        retry_cfg: RetryConfig,
        logger: SessionLogger | None = None,
        wait_until: str = "domcontentloaded",
        nav_timeout_ms: int = 30_000,
        post_load_jitter: tuple[float, float] = (0.8, 2.0),
    ) -> None:
        self.browser = browser
        self.retry_cfg = retry_cfg
        self.logger = logger
        self.wait_until = wait_until
        self.nav_timeout_ms = nav_timeout_ms
        self.post_load_jitter = post_load_jitter

    def fetch(self, url: str) -> PageResult:
        def attempt(_ctx: dict) -> AttemptResult[PageResult]:
            return self._do_fetch(url)

        return run_with_retry(
            url=url,
            fetch=attempt,
            cfg=self.retry_cfg,
            user_agents=self.browser.user_agents,
            logger=self.logger,
        )

    def _do_fetch(self, url: str) -> AttemptResult[PageResult]:
        page: Page | None = None
        try:
            page = self.browser.new_page()
            try:
                response = page.goto(url, wait_until=self.wait_until, timeout=self.nav_timeout_ms)
            except PlaywrightTimeoutError as exc:
                return AttemptResult(
                    None,
                    BlockClassification(
                        BlockType.TIMEOUT,
                        retryable=True,
                        rotate_user_agent=True,
                        reason=str(exc)[:200],
                    ),
                )

            status = response.status if response else None
            status_class = classify_status(status)
            if status_class.type != BlockType.NONE:
                return AttemptResult(None, status_class)

            self.browser.jitter_sleep(page, *self.post_load_jitter)
            html = page.content()
            classification = classify_response(status, html)
            if classification.type != BlockType.NONE:
                return AttemptResult(None, classification)

            return AttemptResult(
                PageResult(url=url, final_url=page.url, status=status, html=html),
                BlockClassification(BlockType.NONE, retryable=False, rotate_user_agent=False),
            )
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass


__all__ = ["PageFetcher", "PageResult", "RetryExhausted"]
