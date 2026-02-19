"""Retry policy decorators and intelligent backoff logic.

This module provides decorator-based retry functionality with exponential backoff,
user agent rotation, and comprehensive event logging. It integrates with BlockDetector
for intelligent retry decisions and RetryLogger for observability.

Key Features:
    - Exponential backoff with configurable delays
    - Automatic user agent rotation on 403/429 responses
    - Smart block detection and non-retryable error handling
    - Cumulative wait time tracking across attempts
    - Comprehensive event logging for debugging
    - Random delays for anti-bot timing
    - Browser-like headers generation

Typical Usage:
    from src.retry_policy import retry_with_backoff

    @retry_with_backoff(max_attempts=5, backoff_strategy="exponential")
    def fetch_data(url):
        response = requests.get(url)
        return response

    # Headers with user agent rotation
    headers = get_browser_headers()
"""

import time
import random
import logging
import os
from functools import wraps
from datetime import datetime
from typing import Callable, Tuple, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryCallState,
)
from requests.exceptions import RequestException, Timeout, ConnectionError
from src.config import (
    MAX_RETRY_ATTEMPTS,
    INITIAL_BACKOFF_DELAY,
    MAX_BACKOFF_DELAY,
    RANDOM_DELAY_RANGE,
)
from src.user_agent_pool import user_agent_pool
from src.block_detector import BlockDetector
from src.models import BlockType, RetryEvent, RetryMetadata
from src.retry_logger import retry_logger

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    backoff_strategy: str = "exponential",
    retry_on: Tuple = (RequestException, Timeout, ConnectionError),
    exclude_on: Tuple = (),
    on_retry: Optional[Callable] = None,
):
    """Decorator factory for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        backoff_strategy: "exponential" or "linear" backoff
        retry_on: Exception types to retry on
        exclude_on: Exception types to never retry
        on_retry: Callback function called on each retry

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Track cumulative wait time across retries
            cumulative_wait = 0.0
            user_agent_rotated_this_attempt = False

            # Custom retry callback
            def before_retry_callback(retry_state: RetryCallState):
                nonlocal cumulative_wait, user_agent_rotated_this_attempt

                attempt = retry_state.attempt_number
                exception = (
                    retry_state.outcome.exception() if retry_state.outcome else None
                )
                exception = exception if isinstance(exception, Exception) else None

                if exception:
                    # Check if it's a blocking response
                    response = getattr(exception, "response", None)
                    block_type = BlockDetector.detect_block_type(
                        response=response, exception=exception
                    )

                    # Skip retry if block is not retryable
                    if block_type and not BlockDetector.is_retryable(block_type):
                        logger.error(
                            f"Non-retryable block detected: {block_type.value}. Stopping retries."
                        )

                        # Log permanent failure event
                        _log_retry_event(
                            attempt=attempt,
                            max_attempts=max_attempts,
                            wait_time=0.0,
                            cumulative_wait=cumulative_wait,
                            user_agent_rotated=False,
                            exception=exception,
                            block_type=block_type,
                            outcome="permanent_failure",
                            kwargs=kwargs,
                        )

                        raise exception

                    # Calculate wait time
                    wait_time = (
                        retry_state.next_action.sleep if retry_state.next_action else 0
                    )
                    cumulative_wait += wait_time

                    # Rotate user agent on 403/429
                    user_agent_rotated_this_attempt = False
                    if block_type and block_type in {
                        BlockType.FORBIDDEN,
                        BlockType.RATE_LIMIT,
                    }:
                        new_agent = user_agent_pool.get_next()
                        user_agent_rotated_this_attempt = True
                        block_value = block_type.value if block_type else "unknown"
                        logger.debug(
                            f"Rotating user agent after {block_value}: {new_agent[:50]}..."
                        )

                    # INFO level: Retry attempt with backoff time
                    logger.info(
                        f"Retrying ({attempt}/{max_attempts}) after {wait_time:.1f}s backoff..."
                    )

                    # WARNING level: Block type and error details
                    if block_type:
                        logger.warning(
                            f"Block type: {block_type.value}. Error: {str(exception)[:100]}"
                        )
                    else:
                        logger.warning(
                            f"Retry due to: {type(exception).__name__}: {str(exception)[:100]}"
                        )

                    # Log retry event
                    _log_retry_event(
                        attempt=attempt,
                        max_attempts=max_attempts,
                        wait_time=wait_time,
                        cumulative_wait=cumulative_wait,
                        user_agent_rotated=user_agent_rotated_this_attempt,
                        exception=exception,
                        block_type=block_type,
                        outcome="retry_scheduled",
                        kwargs=kwargs,
                    )

                    # Call custom callback if provided
                    if on_retry:
                        on_retry(retry_state)

            def _log_retry_event(
                attempt: int,
                max_attempts: int,
                wait_time: float,
                cumulative_wait: float,
                user_agent_rotated: bool,
                exception: Optional[Exception],
                block_type: Optional[BlockType],
                outcome: str,
                kwargs: dict,
            ):
                """Helper to log retry event."""
                # Extract context from kwargs if available
                url = kwargs.get("url") or (
                    args[0]
                    if args and isinstance(args[0], str) and args[0].startswith("http")
                    else None
                )

                # Create retry event
                event = RetryEvent(
                    timestamp=datetime.now().isoformat(),
                    url=url,
                    error_type=type(exception).__name__ if exception else None,
                    error_message=str(exception) if exception else None,
                    retry_metadata=RetryMetadata(
                        attempt=attempt,
                        max_attempts=max_attempts,
                        wait_time=wait_time,
                        cumulative_wait=cumulative_wait,
                        user_agent_rotated=user_agent_rotated,
                    ),
                    outcome=outcome,
                    block_type=block_type.value if block_type else None,
                )

                # Log event
                retry_logger.log_retry_event(event)

            # Custom retry predicate that respects exclude_on
            def should_retry(retry_state: RetryCallState) -> bool:
                """Check if we should retry based on exception type."""
                if not retry_state.outcome or not retry_state.outcome.failed:
                    return False

                exception = (
                    retry_state.outcome.exception() if retry_state.outcome else None
                )

                # Never retry if it's in exclude_on
                if exception and exclude_on and isinstance(exception, exclude_on):
                    logger.error(
                        f"Excluded exception, not retrying: {type(exception).__name__}"
                    )
                    return False

                # Retry if it's in retry_on
                return exception is not None and isinstance(exception, retry_on)

            # Apply tenacity retry decorator
            retry_decorator = retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=INITIAL_BACKOFF_DELAY,
                    min=INITIAL_BACKOFF_DELAY,
                    max=MAX_BACKOFF_DELAY,
                ),
                retry=should_retry,
                before_sleep=before_retry_callback,
                reraise=True,
            )

            retried_func = retry_decorator(func)

            try:
                # Add random delay before request (anti-bot timing)
                if "PYTEST_CURRENT_TEST" not in os.environ and random.random() < 0.8:
                    delay = random.uniform(*RANDOM_DELAY_RANGE)
                    time.sleep(delay)

                result = retried_func(*args, **kwargs)

                # Log success event if there were retries
                if cumulative_wait > 0:
                    _log_retry_event(
                        attempt=0,  # Final successful attempt
                        max_attempts=max_attempts,
                        wait_time=0.0,
                        cumulative_wait=cumulative_wait,
                        user_agent_rotated=user_agent_rotated_this_attempt,
                        exception=None,
                        block_type=None,
                        outcome="success",
                        kwargs=kwargs,
                    )

                return result

            except Exception as e:
                # Check if exception should be excluded from retry
                if exclude_on and isinstance(e, exclude_on):
                    logger.error(
                        f"Excluded exception, not retrying: {type(e).__name__}"
                    )
                    raise

                # ERROR level: Permanent failure after max retries
                logger.error(
                    f"Permanent failure after {max_attempts} retry attempts. "
                    f"Final error: {type(e).__name__}: {str(e)[:100]}"
                )
                raise

        return wrapper

    return decorator


# Legitimate browser headers for FR-010
BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def get_browser_headers(user_agent: Optional[str] = None) -> dict:
    """Get browser headers with optional user agent.

    Args:
        user_agent: User agent string (uses pool if not provided)

    Returns:
        Dictionary of HTTP headers
    """
    headers = BROWSER_HEADERS.copy()
    headers["User-Agent"] = user_agent or user_agent_pool.get_next()
    return headers
