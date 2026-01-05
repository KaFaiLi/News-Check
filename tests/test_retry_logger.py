"""Unit tests for retry logger."""

import pytest
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.models import RetryEvent, RetryMetadata, BlockType


class TestRetryLogger:
    """Test suite for RetryLogger class."""

    def test_log_retry_event_creates_json_file(self, tmp_path):
        """Test log_retry_event() creates JSON file in Output/retry_logs/."""
        from src.retry_logger import RetryLogger
        
        # Create logger with custom output directory
        logger = RetryLogger(output_dir=str(tmp_path))
        
        # Create a retry event
        event = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type="RequestException",
            error_message="Connection timeout",
            retry_metadata=RetryMetadata(
                attempt=1,
                max_attempts=5,
                wait_time=1.0,
                cumulative_wait=1.0,
                user_agent_rotated=False
            ),
            outcome="retry_scheduled"
        )
        
        # Log the event
        logger.log_retry_event(event)
        
        # Verify file was created
        log_dir = tmp_path / "retry_logs"
        assert log_dir.exists()
        
        log_files = list(log_dir.glob("*_retry_log.json"))
        assert len(log_files) == 1
        
        # Verify file contains event
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
            assert "session_id" in log_data
            assert "events" in log_data
            assert len(log_data["events"]) == 1

    def test_log_format_matches_schema(self, tmp_path):
        """Test log format matches schema (session_id, events array, timestamp ISO 8601)."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        event = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type="Timeout",
            error_message="Request timeout",
            retry_metadata=RetryMetadata(
                attempt=1,
                max_attempts=5,
                wait_time=2.0,
                cumulative_wait=2.0,
                user_agent_rotated=True
            ),
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event)
        
        # Read log file
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
        
        # Verify schema
        assert isinstance(log_data["session_id"], str)
        assert isinstance(log_data["events"], list)
        
        # Verify timestamp is ISO 8601
        event_data = log_data["events"][0]
        datetime.fromisoformat(event_data["timestamp"])  # Should not raise

    def test_retry_metadata_includes_all_fields(self, tmp_path):
        """Test retry metadata includes: attempt, max_attempts, wait_time, cumulative_wait, user_agent_rotated."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        metadata = RetryMetadata(
            attempt=3,
            max_attempts=5,
            wait_time=4.0,
            cumulative_wait=7.0,
            user_agent_rotated=True
        )
        
        event = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com/article",
            error_type="RateLimitError",
            error_message="429 Too Many Requests",
            retry_metadata=metadata,
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event)
        
        # Read and verify
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
        
        event_data = log_data["events"][0]
        metadata_data = event_data["retry_metadata"]
        
        assert metadata_data["attempt"] == 3
        assert metadata_data["max_attempts"] == 5
        assert metadata_data["wait_time"] == 4.0
        assert metadata_data["cumulative_wait"] == 7.0
        assert metadata_data["user_agent_rotated"] is True

    def test_multiple_events_appended_to_same_session(self, tmp_path):
        """Test multiple events appended to same session log file."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        # Log first event
        event1 = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com/page1",
            error_type="ConnectionError",
            error_message="Connection failed",
            retry_metadata=RetryMetadata(
                attempt=1,
                max_attempts=5,
                wait_time=1.0,
                cumulative_wait=1.0,
                user_agent_rotated=False
            ),
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event1)
        
        # Log second event
        event2 = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com/page2",
            error_type="Timeout",
            error_message="Request timeout",
            retry_metadata=RetryMetadata(
                attempt=2,
                max_attempts=5,
                wait_time=2.0,
                cumulative_wait=3.0,
                user_agent_rotated=True
            ),
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event2)
        
        # Verify both events in same file
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        assert len(log_files) == 1  # Only one session file
        
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
        
        assert len(log_data["events"]) == 2
        assert log_data["events"][0]["url"] == "https://example.com/page1"
        assert log_data["events"][1]["url"] == "https://example.com/page2"

    def test_error_context_includes_all_fields(self, tmp_path):
        """Test error context includes URL, keyword, article_id, scraper_stage."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        event = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com/article/123",
            keyword="fintech AI",
            article_id="article_123",
            scraper_stage="content_fetch",
            error_type="PlaywrightTimeout",
            error_message="Playwright navigation timeout",
            retry_metadata=RetryMetadata(
                attempt=2,
                max_attempts=5,
                wait_time=2.0,
                cumulative_wait=3.0,
                user_agent_rotated=False
            ),
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event)
        
        # Read and verify
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
        
        event_data = log_data["events"][0]
        assert event_data["url"] == "https://example.com/article/123"
        assert event_data["keyword"] == "fintech AI"
        assert event_data["article_id"] == "article_123"
        assert event_data["scraper_stage"] == "content_fetch"

    def test_outcome_field_correctly_set(self, tmp_path):
        """Test outcome field correctly set: retry_scheduled, success, permanent_failure."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        # Test retry_scheduled
        event1 = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type="RateLimitError",
            error_message="429",
            retry_metadata=RetryMetadata(
                attempt=1,
                max_attempts=5,
                wait_time=1.0,
                cumulative_wait=1.0,
                user_agent_rotated=False
            ),
            outcome="retry_scheduled"
        )
        
        # Test success
        event2 = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type=None,
            error_message=None,
            retry_metadata=RetryMetadata(
                attempt=2,
                max_attempts=5,
                wait_time=2.0,
                cumulative_wait=3.0,
                user_agent_rotated=True
            ),
            outcome="success"
        )
        
        # Test permanent_failure
        event3 = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type="CaptchaDetected",
            error_message="CAPTCHA required",
            retry_metadata=RetryMetadata(
                attempt=5,
                max_attempts=5,
                wait_time=16.0,
                cumulative_wait=31.0,
                user_agent_rotated=False
            ),
            outcome="permanent_failure"
        )
        
        logger.log_retry_event(event1)
        logger.log_retry_event(event2)
        logger.log_retry_event(event3)
        
        # Verify outcomes
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        
        with open(log_files[0], 'r') as f:
            log_data = json.load(f)
        
        assert log_data["events"][0]["outcome"] == "retry_scheduled"
        assert log_data["events"][1]["outcome"] == "success"
        assert log_data["events"][2]["outcome"] == "permanent_failure"

    def test_session_id_uses_correct_format(self, tmp_path):
        """Test session_id uses YYYYMMDD_HHMMSS format."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        # Session ID should be set during initialization
        session_id = logger.session_id
        
        # Verify format: YYYYMMDD_HHMMSS
        assert len(session_id) == 15  # 8 digits + underscore + 6 digits
        assert session_id[8] == "_"
        
        # Parse to verify it's a valid datetime
        datetime.strptime(session_id, "%Y%m%d_%H%M%S")  # Should not raise

    def test_get_session_summary_returns_statistics(self, tmp_path):
        """Test get_session_summary() returns statistics."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        # Log multiple events
        events = [
            RetryEvent(
                timestamp=datetime.now().isoformat(),
                url="https://example.com/1",
                error_type="Timeout",
                error_message="Timeout",
                retry_metadata=RetryMetadata(
                    attempt=1, max_attempts=5, wait_time=1.0,
                    cumulative_wait=1.0, user_agent_rotated=False
                ),
                outcome="retry_scheduled"
            ),
            RetryEvent(
                timestamp=datetime.now().isoformat(),
                url="https://example.com/2",
                error_type=None,
                error_message=None,
                retry_metadata=RetryMetadata(
                    attempt=2, max_attempts=5, wait_time=2.0,
                    cumulative_wait=3.0, user_agent_rotated=True
                ),
                outcome="success"
            ),
            RetryEvent(
                timestamp=datetime.now().isoformat(),
                url="https://example.com/3",
                error_type="RateLimit",
                error_message="429",
                retry_metadata=RetryMetadata(
                    attempt=5, max_attempts=5, wait_time=16.0,
                    cumulative_wait=31.0, user_agent_rotated=False
                ),
                outcome="permanent_failure"
            )
        ]
        
        for event in events:
            logger.log_retry_event(event)
        
        # Get summary
        summary = logger.get_session_summary()
        
        # Verify statistics
        assert "total_retries" in summary
        assert "success_count" in summary
        assert "failure_count" in summary
        assert "avg_wait_time" in summary
        assert "total_cumulative_wait" in summary
        
        assert summary["total_retries"] == 3
        assert summary["success_count"] == 1
        assert summary["failure_count"] == 1

    def test_log_file_path_format(self, tmp_path):
        """Test log file path follows format: Output/retry_logs/{session_id}_retry_log.json."""
        from src.retry_logger import RetryLogger
        
        logger = RetryLogger(output_dir=str(tmp_path))
        
        event = RetryEvent(
            timestamp=datetime.now().isoformat(),
            url="https://example.com",
            error_type="Error",
            error_message="Test error",
            retry_metadata=RetryMetadata(
                attempt=1, max_attempts=5, wait_time=1.0,
                cumulative_wait=1.0, user_agent_rotated=False
            ),
            outcome="retry_scheduled"
        )
        
        logger.log_retry_event(event)
        
        # Check file path format
        log_dir = tmp_path / "retry_logs"
        log_files = list(log_dir.glob("*_retry_log.json"))
        
        assert len(log_files) == 1
        filename = log_files[0].name
        
        # Should be {session_id}_retry_log.json
        assert filename.endswith("_retry_log.json")
        session_id = filename.replace("_retry_log.json", "")
        
        # Verify session_id format
        datetime.strptime(session_id, "%Y%m%d_%H%M%S")
