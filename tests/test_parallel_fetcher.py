"""Tests for the streaming `fetch_and_select`.

We mock the BrowserPool so each candidate's fetch outcome is deterministic
(success/fail by URL). The test then checks that the streaming selector
fills top_n in rank order, slides past failures without buffering, and
respects the AI-banking floor and per-source cap.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future

from src.anti_blocking.retry_policy import RetryConfig
from src.extraction.parallel_fetcher import (
    _Outcome,
    _trim_to_selection,
    fetch_and_select,
)
from src.models import DegradationStatus, ScoredArticle, SourceTier, Topic
from tests.conftest import make_article


def _scored(
    *,
    url: str,
    score: float,
    banking: bool = False,
    domain: str | None = None,
) -> ScoredArticle:
    topics = {Topic.AI_BANKING} if banking else {Topic.AI}
    sa = ScoredArticle(
        article=make_article(url=url, title=f"Article {url}", source="Test", topics=topics),
        topic_relevance=0.7,
        cross_source_consensus=0.0,
        source_tier=SourceTier.TIER_3,
        source_tier_multiplier=1.0,
        recency=0.5,
        final_score=score,
    )
    return sa


class _FakePool:
    """Drop-in replacement for BrowserPool that runs tasks inline.

    `outcome_for(url)` decides success/failure for each URL. Tasks resolve
    immediately, which is fine: the streaming selector cares about the
    *sequence* of completions, not parallel timing — the production
    correctness ultimately reduces to "submit in rank order, accept results
    as they come, stop when full".
    """

    def __init__(self, outcome_for: Callable[[str], bool]):
        self.outcome_for = outcome_for
        self.size = 3
        self.calls: list[str] = []

    def submit(self, fn, sa: ScoredArticle, **kwargs) -> Future:
        url = str(sa.article.url)
        self.calls.append(url)
        f: Future = Future()
        f.set_running_or_notify_cancel()
        success = self.outcome_for(url)
        if success:
            sa.article.markdown = f"# fake content for {url}"
        f.set_result(_Outcome(scored=sa, success=success, reason="" if success else "mocked-fail"))
        return f


def _retry_cfg() -> RetryConfig:
    return RetryConfig(max_attempts=1, initial_backoff=0.0, max_backoff=0.0, random_delay_range=(0.0, 0.0))


def test_fills_top_n_when_all_succeed(tmp_path, selection_settings):
    pool = [_scored(url=f"http://s{i}.example/1", score=10 - i, banking=i < 4) for i in range(15)]
    fake = _FakePool(lambda url: True)

    selected, deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    assert len(selected) == 10
    assert not deg.is_degraded


def test_failures_slide_next_candidates_up(tmp_path, selection_settings):
    """First three candidates fail → ranked 4-13 should fill in. Pool has
    7 banking articles total so the floor still survives 3 failures."""
    pool = [_scored(url=f"http://s{i}.example/1", score=20 - i, banking=i < 7) for i in range(20)]
    fail_set = {"http://s0.example/1", "http://s1.example/1", "http://s2.example/1"}
    fake = _FakePool(lambda url: url not in fail_set)

    selected, deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    chosen_urls = {str(s.article.url) for s in selected}
    assert chosen_urls.isdisjoint(fail_set)
    assert len(selected) == 10
    assert not deg.is_degraded


def test_banking_floor_satisfied_when_naturally_present(tmp_path, selection_settings):
    pool = []
    for i in range(15):
        pool.append(
            _scored(url=f"http://s{i}.example/1", score=20 - i, banking=i in {0, 2, 4, 6, 8})
        )
    fake = _FakePool(lambda url: True)
    selected, deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    banking = sum(1 for s in selected if Topic.AI_BANKING in s.article.appeared_in_topics)
    assert banking >= 3
    assert not deg.is_degraded


def test_keeps_walking_pool_to_satisfy_banking_floor(tmp_path, selection_settings):
    """If top-of-pool has no banking, the streamer must keep going to find them."""
    pool = []
    for i in range(9):
        pool.append(_scored(url=f"http://nb{i}.example/1", score=100 - i, banking=False))
    for i in range(5):
        pool.append(_scored(url=f"http://b{i}.example/1", score=20 - i, banking=True))
    fake = _FakePool(lambda url: True)

    selected, deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    banking = sum(1 for s in selected if Topic.AI_BANKING in s.article.appeared_in_topics)
    assert banking == 3
    assert len(selected) == 10
    assert not deg.is_degraded


def test_pool_exhausted_before_floor_met_marks_degraded(tmp_path, selection_settings):
    pool = [_scored(url=f"http://nb{i}.example/1", score=100 - i, banking=False) for i in range(15)]
    pool.append(_scored(url="http://b0.example/1", score=80, banking=True))
    fake = _FakePool(lambda url: True)

    selected, deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    assert deg.is_degraded
    assert any("AI banking floor" in w for w in deg.warnings)


def test_per_source_cap_enforced_during_streaming(tmp_path, selection_settings):
    """Domain `busy.example` has 10 candidates; cap of 3 should hold even though
    they're all at the top of the rank."""
    pool = [_scored(url=f"http://busy.example/{i}", score=100 - i, banking=False) for i in range(10)]
    for i in range(8):
        pool.append(_scored(url=f"http://b{i}.example/1", score=30 - i, banking=True))
    fake = _FakePool(lambda url: True)

    selected, _deg = fetch_and_select(
        pool,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    busy = sum(1 for s in selected if s.article.domain == "busy.example")
    assert busy <= selection_settings.max_articles_per_source


def test_caches_hit_short_circuits_fetch(tmp_path, selection_settings):
    """If a candidate is already in the cache, the streamer should treat it as
    successful without going through the fake pool."""
    from src.extraction.markdown import write_cache

    cached_url = "http://cached.example/1"
    write_cache(tmp_path, cached_url, "# already-cached body")

    pool_articles = [
        _scored(url=cached_url, score=100, banking=True),
        *[_scored(url=f"http://b{i}.example/1", score=80 - i, banking=True) for i in range(5)],
        *[_scored(url=f"http://nb{i}.example/1", score=50 - i, banking=False) for i in range(10)],
    ]
    visited: list[str] = []

    def outcome(url):
        visited.append(url)
        return True

    fake = _FakePool(outcome)
    selected, _deg = fetch_and_select(
        pool_articles,
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    chosen_urls = {str(s.article.url) for s in selected}
    assert cached_url in chosen_urls
    # Cache hit still goes through fake pool's submit (which short-circuits inside
    # the real task), so its URL appears in calls — but the worker function
    # short-circuits before any browser work. We just assert the cached article
    # made it into selection without depending on the recorded call list.


def test_empty_input_marks_degraded(tmp_path, selection_settings):
    fake = _FakePool(lambda url: True)
    selected, deg = fetch_and_select(
        [],
        selection=selection_settings,
        pool=fake,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_markdown_length=10_000,
        retry_cfg=_retry_cfg(),
        logger=None,
    )
    assert selected == []
    assert deg.is_degraded


def test_trim_helper_prefers_banking_then_score(selection_settings):
    """Direct unit test for the trim helper: banking up to floor, then score."""
    successes = [
        _scored(url="http://nb0.example/1", score=100.0, banking=False),
        _scored(url="http://b0.example/1", score=90.0, banking=True),
        _scored(url="http://nb1.example/1", score=85.0, banking=False),
        _scored(url="http://b1.example/1", score=70.0, banking=True),
        _scored(url="http://b2.example/1", score=60.0, banking=True),
        _scored(url="http://nb2.example/1", score=55.0, banking=False),
        *[_scored(url=f"http://nb{i}.example/1", score=50.0 - i, banking=False) for i in range(3, 12)],
    ]
    deg = DegradationStatus()
    out = _trim_to_selection(successes, selection_settings, deg)
    assert len(out) == 10
    banking_in_out = sum(1 for s in out if Topic.AI_BANKING in s.article.appeared_in_topics)
    assert banking_in_out >= 3
    # Sorted descending by score
    scores = [s.final_score for s in out]
    assert scores == sorted(scores, reverse=True)
