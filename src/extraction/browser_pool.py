"""Thread-pool of Playwright Edge browsers.

Playwright's sync API requires a separate `sync_playwright()` per thread,
so this module spawns N long-lived worker threads, each owning its own
playwright + browser + context lifetime. Tasks are submitted to a queue;
each task is a callable that receives the per-thread `BrowserContext` and
returns a result.

This trades a few seconds of upfront cost (launching N browsers) for
substantial wall-clock savings on multi-fetch workloads, while keeping
identities isolated per thread (separate UA/cookies/locale state).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, TypeVar

from playwright.sync_api import sync_playwright

from src.anti_blocking.user_agents import UserAgentPool
from src.extraction.browser import build_stealth_context, launch_edge

T = TypeVar("T")

# Sentinel pushed to the queue to signal a worker thread to stop.
_SHUTDOWN = object()


class BrowserPool(AbstractContextManager["BrowserPool"]):
    """Pool of Edge browser workers exposing a `submit` API similar to
    `concurrent.futures.Executor`.

    Each task receives the worker's per-thread `BrowserContext` as its
    first positional argument:

        with BrowserPool(workers=3) as pool:
            future = pool.submit(my_task, "http://x")
            result = future.result()
    """

    def __init__(
        self,
        *,
        workers: int,
        headless: bool = True,
        viewport: tuple[int, int] = (1920, 1080),
        locale: str = "en-US",
        timezone_id: str = "America/New_York",
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be >= 1")
        self.workers = workers
        self.headless = headless
        self.viewport = viewport
        self.locale = locale
        self.timezone_id = timezone_id

        self._queue: queue.Queue[Any] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._started = False
        self._shutdown = False

    # ------------- lifecycle -------------

    def __enter__(self) -> BrowserPool:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    def start(self) -> None:
        if self._started:
            return
        for i in range(self.workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"edge-pool-{i}",
                daemon=False,
            )
            t.start()
            self._threads.append(t)
        self._started = True

    def shutdown(self, wait: bool = True) -> None:
        if not self._started or self._shutdown:
            return
        self._shutdown = True
        for _ in self._threads:
            self._queue.put(_SHUTDOWN)
        if wait:
            for t in self._threads:
                t.join(timeout=30)

    # ------------- submission -------------

    def submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """Submit a task. Worker calls `fn(context, *args, **kwargs)`."""
        if self._shutdown:
            raise RuntimeError("BrowserPool is shut down")
        if not self._started:
            self.start()
        future: Future[T] = Future()
        self._queue.put((fn, args, kwargs, future))
        return future

    @property
    def size(self) -> int:
        return self.workers

    # ------------- worker -------------

    def _worker_loop(self) -> None:
        ua_pool = UserAgentPool()
        with sync_playwright() as pw:
            browser = launch_edge(pw, headless=self.headless)
            context = build_stealth_context(
                browser,
                user_agent=ua_pool.current,
                viewport=self.viewport,
                locale=self.locale,
                timezone_id=self.timezone_id,
            )
            try:
                while True:
                    item = self._queue.get()
                    if item is _SHUTDOWN:
                        break
                    fn, args, kwargs, future = item
                    if future.set_running_or_notify_cancel():
                        try:
                            result = fn(context, *args, **kwargs)
                            future.set_result(result)
                        except BaseException as exc:  # noqa: BLE001 — propagate to caller
                            future.set_exception(exc)
                    self._queue.task_done()
            finally:
                try:
                    context.close()
                finally:
                    browser.close()
