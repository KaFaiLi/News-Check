from __future__ import annotations

from unittest.mock import patch

import pytest

from src.anti_blocking.block_detector import BlockClassification, BlockType
from src.anti_blocking.retry_policy import (
    AttemptResult,
    RetryConfig,
    RetryExhausted,
    run_with_retry,
)
from src.anti_blocking.user_agents import UserAgentPool


@pytest.fixture(autouse=True)
def _no_real_sleep():
    """All retry tests should run instantly."""
    with patch("src.anti_blocking.retry_policy.time.sleep"):
        yield


def _ok(value="ok") -> AttemptResult:
    return AttemptResult(
        result=value,
        classification=BlockClassification(BlockType.NONE, retryable=False, rotate_user_agent=False),
    )


def _block(retryable=True, rotate=False, btype=BlockType.RATE_LIMIT) -> AttemptResult:
    return AttemptResult(
        result=None,
        classification=BlockClassification(btype, retryable=retryable, rotate_user_agent=rotate),
    )


def test_returns_immediately_on_first_success():
    pool = UserAgentPool()
    cfg = RetryConfig(max_attempts=5)
    calls: list[int] = []

    def fetch(_ctx):
        calls.append(1)
        return _ok("hello")

    out = run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)
    assert out == "hello"
    assert len(calls) == 1


def test_retries_then_succeeds():
    pool = UserAgentPool()
    cfg = RetryConfig(max_attempts=5)
    seq = [_block(retryable=True, rotate=True), _block(retryable=True, rotate=True), _ok("done")]

    def fetch(_ctx):
        return seq.pop(0)

    out = run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)
    assert out == "done"


def test_rotates_user_agent_when_classification_says_so():
    pool = UserAgentPool()
    starting = pool.current
    cfg = RetryConfig(max_attempts=3)
    seq = [_block(retryable=True, rotate=True), _ok("ok")]

    def fetch(_ctx):
        return seq.pop(0)

    run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)
    # With multi-UA pool, rotate() must change it
    if len({*pool.agents}) > 1:
        assert pool.current != starting


def test_non_retryable_classification_bails_immediately():
    pool = UserAgentPool()
    cfg = RetryConfig(max_attempts=5)
    calls: list[int] = []

    def fetch(_ctx):
        calls.append(1)
        return _block(retryable=False, btype=BlockType.CAPTCHA)

    with pytest.raises(RetryExhausted) as exc_info:
        run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)
    assert exc_info.value.last_classification is not None
    assert exc_info.value.last_classification.type is BlockType.CAPTCHA
    assert len(calls) == 1


def test_exhausts_max_attempts():
    pool = UserAgentPool()
    cfg = RetryConfig(max_attempts=3)

    def fetch(_ctx):
        return _block(retryable=True, rotate=True)

    with pytest.raises(RetryExhausted):
        run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)


def test_exception_inside_fetch_is_classified_and_retried():
    pool = UserAgentPool()
    cfg = RetryConfig(max_attempts=2)

    def fetch(_ctx):
        raise RuntimeError("boom")

    with pytest.raises(RetryExhausted):
        run_with_retry(url="http://x", fetch=fetch, cfg=cfg, user_agents=pool)
