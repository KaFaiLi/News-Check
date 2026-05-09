"""Playwright Edge browser launcher with stealth-style anti-bot countermeasures."""

from __future__ import annotations

import random
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from src.anti_blocking.user_agents import UserAgentPool

_STEALTH_INIT_SCRIPT = """
// Hide automation flag.
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Spoof languages.
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// Spoof plugins (non-empty array).
Object.defineProperty(navigator, 'plugins', {
    get: () => [{ name: 'Chrome PDF Plugin' }, { name: 'Chrome PDF Viewer' }, { name: 'Native Client' }],
});

// Patch chrome runtime indicator.
window.chrome = window.chrome || { runtime: {} };

// Permissions query: notifications.
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
}
"""


_LAUNCH_ARGS: tuple[str, ...] = (
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
)


def launch_edge(pw: Playwright, *, headless: bool) -> Browser:
    """Launch a Playwright browser pinned to the Edge channel."""
    return pw.chromium.launch(channel="msedge", headless=headless, args=list(_LAUNCH_ARGS))


def build_stealth_context(
    browser: Browser,
    *,
    user_agent: str,
    viewport: tuple[int, int] = (1920, 1080),
    locale: str = "en-US",
    timezone_id: str = "America/New_York",
) -> BrowserContext:
    """Build a Playwright BrowserContext with stealth init script + IB-friendly headers."""
    context = browser.new_context(
        user_agent=user_agent,
        viewport={"width": viewport[0], "height": viewport[1]},
        locale=locale,
        timezone_id=timezone_id,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    context.add_init_script(_STEALTH_INIT_SCRIPT)
    return context


def settle_after_load(page: Page, *, timeout_ms: int = 2000) -> None:
    """Wait for the page to go quiet (no network activity), capped at timeout_ms.
    Returns earlier if the network already settled."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # Some sites never reach networkidle (long-poll, ads); we accept whatever's loaded.
        pass


class EdgeBrowser(AbstractContextManager["EdgeBrowser"]):
    """Context-managed Playwright session pinned to the Edge channel."""

    def __init__(
        self,
        user_agents: UserAgentPool,
        headless: bool = True,
        viewport: tuple[int, int] = (1920, 1080),
        locale: str = "en-US",
        timezone_id: str = "America/New_York",
    ) -> None:
        self.user_agents = user_agents
        self.headless = headless
        self.viewport = viewport
        self.locale = locale
        self.timezone_id = timezone_id

        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> EdgeBrowser:
        self._pw = sync_playwright().start()
        self._browser = launch_edge(self._pw, headless=self.headless)
        self._make_context()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            self._context = None
        try:
            if self._browser:
                self._browser.close()
        finally:
            self._browser = None
        try:
            if self._pw:
                self._pw.stop()
        finally:
            self._pw = None

    def _make_context(self) -> None:
        assert self._browser is not None
        if self._context:
            self._context.close()
        self._context = build_stealth_context(
            self._browser,
            user_agent=self.user_agents.current,
            viewport=self.viewport,
            locale=self.locale,
            timezone_id=self.timezone_id,
        )

    def rotate_identity(self) -> None:
        """Rotate UA and rebuild the browser context so cookies don't leak across identities."""
        self.user_agents.rotate()
        self._make_context()

    def new_page(self) -> Page:
        if self._context is None:
            raise RuntimeError("EdgeBrowser used outside its context manager")
        return self._context.new_page()

    @staticmethod
    def jitter_sleep(page: Page, low: float = 0.5, high: float = 1.5) -> None:
        """Wait a randomized human-ish duration via the page's clock."""
        page.wait_for_timeout(int(random.uniform(low, high) * 1000))

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("EdgeBrowser used outside its context manager")
        return self._context

    @property
    def info(self) -> dict[str, Any]:
        return {
            "channel": "msedge",
            "headless": self.headless,
            "user_agent": self.user_agents.current,
            "viewport": self.viewport,
            "locale": self.locale,
            "timezone": self.timezone_id,
        }
