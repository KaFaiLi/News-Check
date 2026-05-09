"""Retry policy: exponential backoff + UA rotation, driven by `BlockClassification`.

`run_with_retry` is the single entry point. Pass it a callable that takes a
"context" dict (mutated with `user_agent` per attempt) and returns
`(result, classification)`. The runner keeps retrying until success or
exhaustion, rotating UAs and waiting per the schedule.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from src.anti_blocking.block_detector import (
    BlockClassification,
    BlockType,
    classify_exception,
)
from src.anti_blocking.session_logger import SessionLogger
from src.anti_blocking.user_agents import UserAgentPool

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 5
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    random_delay_range: tuple[float, float] = (1.0, 5.0)


class RetryExhausted(Exception):
    def __init__(self, url: str, last_classification: BlockClassification | None) -> None:
        self.url = url
        self.last_classification = last_classification
        super().__init__(
            f"Retries exhausted for {url}; "
            f"last block: {last_classification.type if last_classification else 'unknown'}"
        )


@dataclass
class AttemptResult(Generic[T]):
    result: T | None
    classification: BlockClassification


def _backoff_seconds(attempt: int, cfg: RetryConfig) -> float:
    base = min(cfg.initial_backoff * (2 ** (attempt - 1)), cfg.max_backoff)
    jitter = random.uniform(0, base * 0.25)
    return base + jitter


def _human_delay(cfg: RetryConfig) -> float:
    lo, hi = cfg.random_delay_range
    return random.uniform(lo, hi)


def run_with_retry(
    *,
    url: str,
    fetch: Callable[[dict[str, Any]], AttemptResult[T]],
    cfg: RetryConfig,
    user_agents: UserAgentPool,
    logger: SessionLogger | None = None,
    pre_attempt_delay: bool = True,
) -> T:
    """Invoke `fetch` with retries until success, raising RetryExhausted otherwise."""

    last_class: BlockClassification | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        if pre_attempt_delay and attempt == 1:
            time.sleep(_human_delay(cfg))

        ctx: dict[str, Any] = {"user_agent": user_agents.current, "attempt": attempt}

        try:
            outcome = fetch(ctx)
        except Exception as exc:  # noqa: BLE001 — we deliberately re-classify any error
            classification = classify_exception(exc)
            outcome = AttemptResult(result=None, classification=classification)

        last_class = outcome.classification

        if outcome.classification.type == BlockType.NONE and outcome.result is not None:
            if logger:
                logger.log_success(url=url, attempts=attempt)
            return outcome.result

        if not outcome.classification.retryable or attempt == cfg.max_attempts:
            if logger:
                logger.log_failure(url=url, reason=outcome.classification.reason or outcome.classification.type.value)
            raise RetryExhausted(url=url, last_classification=outcome.classification)

        wait = _backoff_seconds(attempt, cfg)
        rotated = False
        if outcome.classification.rotate_user_agent:
            user_agents.rotate()
            rotated = True

        if logger:
            logger.log_retry(
                url=url,
                attempt=attempt,
                max_attempts=cfg.max_attempts,
                block_type=outcome.classification.type.value,
                wait_seconds=wait,
                rotated_user_agent=rotated,
            )

        time.sleep(wait)

    raise RetryExhausted(url=url, last_classification=last_class)
