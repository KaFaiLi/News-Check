"""Unit tests for blocking detection."""

import pytest
from unittest.mock import Mock
from requests.exceptions import Timeout, ConnectionError
from src.block_detector import BlockDetector
from src.models import BlockType


class TestBlockDetector:
    """Test suite for BlockDetector class."""

    def test_rate_limit_detection_429(self):
        """Test rate limit detection (HTTP 429)."""
        response = Mock()
        response.status_code = 429
        
        block_type = BlockDetector.detect_block_type(response=response)
        
        assert block_type == BlockType.RATE_LIMIT

    def test_forbidden_detection_403(self):
        """Test forbidden detection (HTTP 403)."""
        response = Mock()
        response.status_code = 403
        
        block_type = BlockDetector.detect_block_type(response=response)
        
        assert block_type == BlockType.FORBIDDEN

    def test_captcha_detection_html_content(self):
        """Test CAPTCHA detection (HTML content match: 'captcha', 'recaptcha')."""
        response = Mock()
        response.status_code = 200
        response.text = "<html><body><div class='g-recaptcha'>Please verify you are human</div></body></html>"
        
        block_type = BlockDetector.detect_block_type(response=response, html_content=response.text)
        
        assert block_type == BlockType.CAPTCHA

    def test_captcha_detection_case_insensitive(self):
        """Test CAPTCHA detection is case-insensitive."""
        response = Mock()
        response.status_code = 200
        response.text = "<html><body>CAPTCHA Required</body></html>"
        
        block_type = BlockDetector.detect_block_type(response=response, html_content=response.text)
        
        assert block_type == BlockType.CAPTCHA

    def test_timeout_detection_timeout_exception(self):
        """Test timeout detection (Timeout exception)."""
        exception = Timeout("Request timed out")
        
        block_type = BlockDetector.detect_block_type(exception=exception)
        
        assert block_type == BlockType.TIMEOUT

    def test_connection_error_detection(self):
        """Test connection error detection (ConnectionError exception)."""
        exception = ConnectionError("Connection refused")
        
        block_type = BlockDetector.detect_block_type(exception=exception)
        
        assert block_type == BlockType.CONNECTION_ERROR

    def test_server_error_detection_5xx(self):
        """Test server error detection (5xx status codes)."""
        for status_code in [500, 502, 503, 504]:
            response = Mock()
            response.status_code = status_code
            
            block_type = BlockDetector.detect_block_type(response=response)
            
            assert block_type == BlockType.SERVER_ERROR, f"Status {status_code} should be SERVER_ERROR"

    def test_non_retryable_detection_404(self):
        """Test non-retryable detection (404, 410, 401)."""
        for status_code in [404, 410, 401]:
            response = Mock()
            response.status_code = status_code
            
            block_type = BlockDetector.detect_block_type(response=response)
            
            assert block_type == BlockType.NON_RETRYABLE, f"Status {status_code} should be NON_RETRYABLE"

    def test_detect_block_type_returns_correct_enum(self):
        """Test detect_block_type() returns correct BlockType enum."""
        response = Mock()
        response.status_code = 429
        
        result = BlockDetector.detect_block_type(response=response)
        
        assert isinstance(result, BlockType)
        assert result.value == "rate_limit"

    def test_is_retryable_returns_false_for_captcha(self):
        """Test is_retryable() returns False for CAPTCHA."""
        assert BlockDetector.is_retryable(BlockType.CAPTCHA) is False

    def test_is_retryable_returns_false_for_non_retryable(self):
        """Test is_retryable() returns False for NON_RETRYABLE."""
        assert BlockDetector.is_retryable(BlockType.NON_RETRYABLE) is False

    def test_is_retryable_returns_true_for_rate_limit(self):
        """Test is_retryable() returns True for RATE_LIMIT."""
        assert BlockDetector.is_retryable(BlockType.RATE_LIMIT) is True

    def test_is_retryable_returns_true_for_timeout(self):
        """Test is_retryable() returns True for TIMEOUT."""
        assert BlockDetector.is_retryable(BlockType.TIMEOUT) is True

    def test_get_retry_strategy_exponential_for_rate_limit(self):
        """Test get_retry_strategy() returns 'exponential' for RATE_LIMIT."""
        strategy = BlockDetector.get_retry_strategy(BlockType.RATE_LIMIT)
        assert strategy == "exponential"

    def test_get_retry_strategy_linear_for_timeout(self):
        """Test get_retry_strategy() returns 'linear' for TIMEOUT."""
        strategy = BlockDetector.get_retry_strategy(BlockType.TIMEOUT)
        assert strategy == "linear"

    def test_empty_html_content_detection(self):
        """Test empty response detection as INVALID_HTML."""
        response = Mock()
        response.status_code = 200
        response.text = ""
        
        block_type = BlockDetector.detect_block_type(response=response, html_content="")
        
        assert block_type == BlockType.INVALID_HTML

    def test_none_response_and_exception_returns_none(self):
        """Test None response and exception returns None (no block detected)."""
        block_type = BlockDetector.detect_block_type(response=None, exception=None)
        
        assert block_type is None

    def test_normal_200_response_returns_none(self):
        """Test normal 200 response with valid content returns None."""
        response = Mock()
        response.status_code = 200
        response.text = "<html><body><h1>Normal Page</h1></body></html>"
        
        block_type = BlockDetector.detect_block_type(response=response, html_content=response.text)
        
        assert block_type is None
