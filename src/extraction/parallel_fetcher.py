"""Streaming, parallel article fetcher with rank-order backfill.

Walks a ranked candidate pool in score-descending order and submits
extractions to a `BrowserPool`. Failed extractions are simply not counted —
the next-ranked candidate slides up. Stops once we have `top_n` successful
extractions that satisfy the AI-banking floor and per-source cap.

In-flight fetches at the moment we cross the threshold are still awaited
(can't cancel a Playwright navigation), and any extra successes are
trimmed off when we build the final list.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext
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
from src.anti_blocking.user_agents import UserAgentPool
from src.config import SelectionSettings
from src.extraction.browser import settle_after_load
from src.extraction.browser_pool import BrowserPool
from src.extraction.markdown import html_to_markdown, read_cache, write_cache
from src.models import DegradationStatus, ScoredArticle, Topic


@dataclass
class _Outcome:
    scored: ScoredArticle
    success: bool
    reason: str = ""


def _is_banking(sa: ScoredArticle) -> bool:
    return Topic.AI_BANKING in sa.article.appeared_in_topics or (
        sa.article.discovered_via_topic == Topic.AI_BANKING
    )


def _fetch_html_in_context(
    context: BrowserContext,
    url: str,
    *,
    nav_timeout_ms: int = 30_000,
    wait_until: str = "domcontentloaded",
) -> AttemptResult:
    """Single-attempt fetch using a thread-local browser context."""
    page = context.new_page()
    try:
        try:
            response = page.goto(url, wait_until=wait_until, timeout=nav_timeout_ms)
        except PlaywrightTimeoutError as exc:
            return AttemptResult(
                None,
                BlockClassification(
                    BlockType.TIMEOUT,
                    retryable=True,
                    rotate_user_agent=False,
                    reason=str(exc)[:200],
                ),
            )

        status = response.status if response else None
        sc = classify_status(status)
        if sc.type != BlockType.NONE:
            return AttemptResult(None, sc)

        settle_after_load(page, timeout_ms=2000)
        html = page.content()
        cls = classify_response(status, html)
        if cls.type != BlockType.NONE:
            return AttemptResult(None, cls)
        return AttemptResult(
            html,
            BlockClassification(BlockType.NONE, retryable=False, rotate_user_agent=False),
        )
    finally:
        try:
            page.close()
        except Exception:
            pass


# Module-level shared UA pool — `run_with_retry` rotates this on retry, but
# the browser context's UA is fixed at context creation, so rotation is a
# no-op for our parallel path. The pool is passed only to satisfy the API.
_DUMMY_UA_POOL = UserAgentPool()


def _extract_one_task(
    context: BrowserContext,
    sa: ScoredArticle,
    *,
    cache_dir: Path,
    max_markdown_length: int,
    retry_cfg: RetryConfig,
    logger: SessionLogger | None,
) -> _Outcome:
    """Body of a single extraction task. Runs inside a worker thread."""
    url = str(sa.article.url)

    cached = read_cache(cache_dir, url)
    if cached:
        sa.article.markdown = cached
        return _Outcome(scored=sa, success=True, reason="cache-hit")

    def attempt(_ctx_unused: dict) -> AttemptResult:
        return _fetch_html_in_context(context, url)

    try:
        html = run_with_retry(
            url=url,
            fetch=attempt,
            cfg=retry_cfg,
            user_agents=_DUMMY_UA_POOL,
            logger=logger,
            pre_attempt_delay=False,
        )
    except RetryExhausted as exc:
        return _Outcome(
            scored=sa,
            success=False,
            reason=f"retry-exhausted:{exc.last_classification.type.value if exc.last_classification else 'unknown'}",
        )
    except Exception as exc:  # noqa: BLE001
        return _Outcome(scored=sa, success=False, reason=f"error:{exc.__class__.__name__}")

    md = html_to_markdown(html, max_chars=max_markdown_length)
    if not md:
        return _Outcome(scored=sa, success=False, reason="empty-markdown")

    write_cache(cache_dir, url, md)
    sa.article.markdown = md
    return _Outcome(scored=sa, success=True)


def fetch_and_select(
    ranked: list[ScoredArticle],
    *,
    selection: SelectionSettings,
    pool: BrowserPool,
    cache_dir: Path,
    max_markdown_length: int,
    retry_cfg: RetryConfig,
    logger: SessionLogger | None,
    degradation: DegradationStatus | None = None,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> tuple[list[ScoredArticle], DegradationStatus]:
    """Stream extraction over `ranked` until we have a final selection.

    Selection rules (all enforced live):
      * `selection.top_n` total successful articles
      * at least `selection.ai_banking_minimum_floor` of those are AI-banking
      * at most `selection.max_articles_per_source` per domain (counted
        from successes)

    On exhaustion of the candidate pool before the rules are satisfied,
    the returned list contains whatever succeeded and a `DegradationStatus`
    warning is recorded.

    `on_progress(submitted, succeeded, failed)` is invoked after each
    completion if provided, for caller-side logging.
    """
    if degradation is None:
        degradation = DegradationStatus()

    if not ranked:
        degradation.is_degraded = True
        degradation.add_warning("Ranking produced no candidates; nothing to extract.")
        return [], degradation

    successes: list[ScoredArticle] = []
    domain_success: Counter[str] = Counter()
    submitted = 0
    failed = 0
    candidate_iter = iter(ranked)
    pending: dict[Future, ScoredArticle] = {}
    deferred_non_banking: list[ScoredArticle] = []

    non_banking_budget = max(0, selection.top_n - selection.ai_banking_minimum_floor)

    def banking_count() -> int:
        return sum(1 for s in successes if _is_banking(s))

    def banking_in_flight() -> int:
        return sum(1 for sa in pending.values() if _is_banking(sa))

    def non_banking_load() -> int:
        # Successes + in-flight that, on success, would land in non-banking.
        return (len(successes) - banking_count()) + (len(pending) - banking_in_flight())

    def have_enough() -> bool:
        if len(successes) < selection.top_n:
            return False
        return banking_count() >= selection.ai_banking_minimum_floor

    def submit_next(*, allow_overflow: bool = False) -> bool:
        # Topic-aware submission. We reserve `ai_banking_minimum_floor` slots
        # for banking by capping non-banking submissions+in-flight at
        # `top_n - floor`. This keeps banking eligible to fill the floor
        # even when banking articles rank below non-banking ones, and
        # bounds total fetches near top_n + a small in-flight buffer.
        # Skipped non-banking candidates are stashed in `deferred_non_banking`
        # so the fallback pass can use them if banking turns out to be too
        # thin to meet the floor.
        nonlocal submitted
        for sa in candidate_iter:
            domain = sa.article.domain or "unknown"
            if domain_success[domain] >= selection.max_articles_per_source:
                continue
            if (
                not allow_overflow
                and not _is_banking(sa)
                and non_banking_load() >= non_banking_budget
            ):
                deferred_non_banking.append(sa)
                continue
            future = pool.submit(
                _extract_one_task,
                sa,
                cache_dir=cache_dir,
                max_markdown_length=max_markdown_length,
                retry_cfg=retry_cfg,
                logger=logger,
            )
            pending[future] = sa
            submitted += 1
            return True
        return False

    def submit_next_deferred() -> bool:
        nonlocal submitted
        while deferred_non_banking:
            sa = deferred_non_banking.pop(0)
            domain = sa.article.domain or "unknown"
            if domain_success[domain] >= selection.max_articles_per_source:
                continue
            future = pool.submit(
                _extract_one_task,
                sa,
                cache_dir=cache_dir,
                max_markdown_length=max_markdown_length,
                retry_cfg=retry_cfg,
                logger=logger,
            )
            pending[future] = sa
            submitted += 1
            return True
        return False

    def consume(fut: Future) -> None:
        nonlocal failed
        sa = pending.pop(fut)
        try:
            outcome: _Outcome = fut.result()
        except BaseException as exc:
            outcome = _Outcome(
                scored=sa, success=False, reason=f"crash:{exc.__class__.__name__}"
            )
        degradation.record_attempt(success=outcome.success)
        if outcome.success:
            domain = outcome.scored.article.domain or "unknown"
            # With parallel submissions we may overshoot the cap; drop in that case.
            if domain_success[domain] < selection.max_articles_per_source:
                successes.append(outcome.scored)
                domain_success[domain] += 1
        else:
            failed += 1
        if on_progress is not None:
            on_progress(submitted, len(successes), failed)

    for _ in range(pool.size):
        if not submit_next():
            break

    while pending and not have_enough():
        done, _ = wait(set(pending), return_when=FIRST_COMPLETED)
        for fut in done:
            consume(fut)
            if not have_enough():
                submit_next()

    # Fallback: candidate pool is exhausted (or only non-banking left) and we
    # still don't have top_n successes. The deferred non-banking pile is the
    # remainder we held back to keep room for banking; release it now to top
    # up. (If banking turned out to be plentiful, this list is empty.)
    if not have_enough() and len(successes) < selection.top_n:
        for _ in range(pool.size):
            if not submit_next_deferred():
                break
        while pending and len(successes) < selection.top_n:
            done, _ = wait(set(pending), return_when=FIRST_COMPLETED)
            for fut in done:
                consume(fut)
                if len(successes) < selection.top_n:
                    submit_next_deferred()

    for fut in list(pending):
        consume(fut)

    final = _trim_to_selection(successes, selection, degradation)
    degradation.collected_results_count = len(final)
    return final, degradation


def _trim_to_selection(
    successes: list[ScoredArticle],
    selection: SelectionSettings,
    degradation: DegradationStatus,
) -> list[ScoredArticle]:
    """Reduce successes to exactly `top_n`, prioritising AI-banking up to
    the floor, then highest score. Records a degradation warning if the
    floor is unmet."""
    if not successes:
        degradation.is_degraded = True
        degradation.add_warning("No articles successfully extracted.")
        return []

    # Sort by final_score desc as the master order.
    by_score = sorted(successes, key=lambda s: s.final_score, reverse=True)

    banking = [s for s in by_score if _is_banking(s)]
    floor = min(selection.ai_banking_minimum_floor, len(banking))
    n = selection.top_n

    chosen = banking[:floor]
    remaining_slots = max(0, n - len(chosen))
    chosen_urls = {str(s.article.url) for s in chosen}
    fillers = [s for s in by_score if str(s.article.url) not in chosen_urls][:remaining_slots]
    chosen.extend(fillers)

    chosen.sort(key=lambda s: s.final_score, reverse=True)

    if floor < selection.ai_banking_minimum_floor:
        degradation.is_degraded = True
        degradation.add_warning(
            f"AI banking floor not met: only {floor} of "
            f"{selection.ai_banking_minimum_floor} AI-banking articles successfully extracted."
        )

    if len(chosen) < selection.top_n:
        degradation.is_degraded = True
        degradation.add_warning(
            f"Top-{selection.top_n} not filled: only {len(chosen)} articles "
            f"survived extraction."
        )

    return chosen
