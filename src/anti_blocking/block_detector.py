"""Classify HTTP responses and rendered pages into block categories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BlockType(StrEnum):
    NONE = "none"
    RATE_LIMIT = "rate_limit"          # 429
    FORBIDDEN = "forbidden"            # 403
    SERVER_ERROR = "server_error"      # 5xx
    CAPTCHA = "captcha"                # detected via body text
    TIMEOUT = "timeout"
    EMPTY_BODY = "empty_body"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BlockClassification:
    type: BlockType
    retryable: bool
    rotate_user_agent: bool
    reason: str = ""


_CAPTCHA_MARKERS = (
    "captcha",
    "are you a robot",
    "verify you are human",
    "unusual traffic",
    "cf-challenge",
    "cloudflare ray id",
    "press and hold",
)


def classify_status(status: int | None) -> BlockClassification:
    """Classify a numeric HTTP status into a block category."""
    if status is None:
        return BlockClassification(BlockType.UNKNOWN, retryable=True, rotate_user_agent=False)
    if 200 <= status < 300:
        return BlockClassification(BlockType.NONE, retryable=False, rotate_user_agent=False)
    if status == 429:
        return BlockClassification(
            BlockType.RATE_LIMIT, retryable=True, rotate_user_agent=True, reason="HTTP 429"
        )
    if status == 403:
        return BlockClassification(
            BlockType.FORBIDDEN, retryable=True, rotate_user_agent=True, reason="HTTP 403"
        )
    if 500 <= status < 600:
        return BlockClassification(
            BlockType.SERVER_ERROR, retryable=True, rotate_user_agent=False, reason=f"HTTP {status}"
        )
    if 400 <= status < 500:
        # 4xx other than 403/429 — generally not retryable
        return BlockClassification(
            BlockType.UNKNOWN, retryable=False, rotate_user_agent=False, reason=f"HTTP {status}"
        )
    return BlockClassification(BlockType.UNKNOWN, retryable=True, rotate_user_agent=False)


def classify_text(body: str | None) -> BlockClassification:
    """Detect CAPTCHA-style challenge pages from body text."""
    if not body or not body.strip():
        return BlockClassification(
            BlockType.EMPTY_BODY, retryable=True, rotate_user_agent=True, reason="empty body"
        )
    lowered = body.lower()
    for marker in _CAPTCHA_MARKERS:
        if marker in lowered:
            return BlockClassification(
                BlockType.CAPTCHA,
                retryable=False,
                rotate_user_agent=False,
                reason=f"matched '{marker}'",
            )
    return BlockClassification(BlockType.NONE, retryable=False, rotate_user_agent=False)


def classify_response(status: int | None, body: str | None) -> BlockClassification:
    """Combine status and body checks; the more severe classification wins."""
    by_status = classify_status(status)
    if by_status.type != BlockType.NONE:
        return by_status
    return classify_text(body)


def classify_exception(exc: BaseException) -> BlockClassification:
    """Map an exception (e.g. PlaywrightTimeoutError) to a classification."""
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return BlockClassification(
            BlockType.TIMEOUT, retryable=True, rotate_user_agent=True, reason=str(exc)[:200]
        )
    return BlockClassification(
        BlockType.UNKNOWN, retryable=True, rotate_user_agent=False, reason=str(exc)[:200]
    )
