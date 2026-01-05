"""Unit tests for retry policy decorator."""

import pytest
import time
from unittest.mock import Mock, patch, call
from requests.exceptions import RequestException, Timeout, ConnectionError
from src.retry_policy import retry_with_backoff
from src.models import BlockType


class TestRetryPolicy:
    """Test suite for retry_with_backoff decorator."""

    @patch('src.retry_policy.random.uniform', return_value=0.1)
    @patch('src.retry_policy.random.random', return_value=0.9)  # Always trigger random delay
    def test_exponential_backoff_delays(self, mock_random, mock_uniform):
        """Test exponential backoff delays: 1s, 2s, 4s, 8s, 16s (capped at 60s)."""
        mock_func = Mock(side_effect=[RequestException(), RequestException(), "success"])
        decorated = retry_with_backoff(max_attempts=3)(mock_func)
        
        start_time = time.time()
        result = decorated()
        elapsed = time.time() - start_time
        
        # Should have waited ~1s + ~2s + random delays = ~3.3s (with tolerance for random delays)
        assert 2.5 < elapsed < 5.0, f"Expected ~3-4s delay with random, got {elapsed}s"
        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retry_attempts_enforcement(self):
        """Test max retry attempts enforcement (5 attempts then raise)."""
        mock_func = Mock(side_effect=RequestException("Always fails"))
        decorated = retry_with_backoff(max_attempts=5)(mock_func)
        
        with pytest.raises(RequestException, match="Always fails"):
            decorated()
        
        # Should have tried 5 times
        assert mock_func.call_count == 5

    def test_successful_retry_after_second_attempt(self):
        """Test successful retry after 2nd attempt."""
        mock_func = Mock(side_effect=[RequestException(), "success"])
        decorated = retry_with_backoff(max_attempts=5)(mock_func)
        
        result = decorated()
        
        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_on_exception_filtering(self):
        """Test retry_on exception filtering (retries RequestException, not ValueError)."""
        # Should retry on RequestException
        mock_func1 = Mock(side_effect=[RequestException(), "success"])
        decorated1 = retry_with_backoff(max_attempts=3, retry_on=(RequestException,))(mock_func1)
        result1 = decorated1()
        assert result1 == "success"
        
        # Should NOT retry on ValueError - raise immediately
        mock_func2 = Mock(side_effect=ValueError("Invalid"))
        decorated2 = retry_with_backoff(max_attempts=3, retry_on=(RequestException,))(mock_func2)
        
        with pytest.raises(ValueError, match="Invalid"):
            decorated2()
        
        # Should only call once (no retry)
        assert mock_func2.call_count == 1

    def test_exclude_on_exception_bypass(self):
        """Test exclude_on exception bypass (CAPTCHA skips retry)."""
        # Create a custom exception to simulate CAPTCHA
        class CaptchaDetected(Exception):
            pass
        
        mock_func = Mock(side_effect=CaptchaDetected("CAPTCHA required"))
        decorated = retry_with_backoff(
            max_attempts=5, 
            retry_on=(Exception,),
            exclude_on=(CaptchaDetected,)
        )(mock_func)
        
        with pytest.raises(CaptchaDetected, match="CAPTCHA required"):
            decorated()
        
        # Should only call once (no retry due to exclude_on)
        assert mock_func.call_count == 1

    def test_on_retry_callback_invocation(self):
        """Test on_retry callback invocation with correct context."""
        callback_mock = Mock()
        mock_func = Mock(side_effect=[RequestException("Error"), "success"])
        
        decorated = retry_with_backoff(
            max_attempts=3,
            on_retry=callback_mock
        )(mock_func)
        
        result = decorated()
        
        assert result == "success"
        # Callback should be invoked once (after first failure)
        assert callback_mock.call_count == 1
        
        # Check callback was called with retry context
        call_args = callback_mock.call_args[0][0]
        assert hasattr(call_args, 'attempt_number')
        assert call_args.attempt_number == 2  # Second attempt

    def test_timeout_exception_triggers_retry(self):
        """Test Timeout exception triggers retry."""
        mock_func = Mock(side_effect=[Timeout(), "success"])
        decorated = retry_with_backoff(max_attempts=3, retry_on=(Timeout,))(mock_func)
        
        result = decorated()
        
        assert result == "success"
        assert mock_func.call_count == 2

    def test_connection_error_triggers_retry(self):
        """Test ConnectionError triggers retry."""
        mock_func = Mock(side_effect=[ConnectionError(), "success"])
        decorated = retry_with_backoff(max_attempts=3, retry_on=(ConnectionError,))(mock_func)
        
        result = decorated()
        
        assert result == "success"
        assert mock_func.call_count == 2

    def test_first_attempt_success_no_retry(self):
        """Test first attempt success requires no retry."""
        mock_func = Mock(return_value="success")
        decorated = retry_with_backoff(max_attempts=5)(mock_func)
        
        start_time = time.time()
        result = decorated()
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert mock_func.call_count == 1
        # Should be nearly instant (no backoff delay)
        assert elapsed < 0.5

    def test_backoff_cap_at_max_delay(self):
        """Test backoff is capped at MAX_BACKOFF_DELAY (60s)."""
        # Mock time.sleep to track delays
        with patch('time.sleep') as mock_sleep:
            mock_func = Mock(side_effect=[RequestException()] * 10 + ["success"])
            decorated = retry_with_backoff(max_attempts=11)(mock_func)
            
            result = decorated()
            
            assert result == "success"
            
            # Check that delays are capped at 60s
            # Exponential: 1, 2, 4, 8, 16, 32, 64(→60), 128(→60), ...
            delays = [call[0][0] for call in mock_sleep.call_args_list]
            assert all(delay <= 60 for delay in delays), f"Delays exceeded 60s cap: {delays}"
