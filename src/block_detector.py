"""Blocking detection and classification module.

This module provides intelligent detection and classification of various types of
blocking responses from web servers during scraping operations. It categorizes blocks
into retryable and non-retryable types to enable smart retry logic.

Key Features:
    - HTTP status code detection (403, 429, 5xx, etc.)
    - CAPTCHA pattern recognition in HTML content
    - Network error classification (timeouts, connection errors)
    - Retry strategy recommendations per block type
    - Empty/invalid HTML detection

Typical Usage:
    from src.block_detector import BlockDetector
    
    block_type = BlockDetector.detect_block_type(
        response=response,
        exception=exception,
        html_content=html_content
    )
    
    if block_type and BlockDetector.is_retryable(block_type):
        # Retry with appropriate strategy
        strategy = BlockDetector.get_retry_strategy(block_type)
"""

import re
from typing import Optional
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError
from src.models import BlockType


class BlockDetector:
    """Detects and classifies blocking responses."""
    
    # CAPTCHA detection patterns
    CAPTCHA_PATTERNS = [
        r'captcha',
        r'recaptcha',
        r'g-recaptcha',
        r'bot.*detection',
        r'verify.*human',
        r'please.*verify',
    ]
    
    @staticmethod
    def detect_block_type(
        response=None,
        exception: Optional[Exception] = None,
        html_content: Optional[str] = None
    ) -> Optional[BlockType]:
        """Detect and classify blocking type.
        
        Args:
            response: HTTP response object (if available)
            exception: Exception raised (if any)
            html_content: HTML content to analyze (if available)
            
        Returns:
            BlockType enum value or None if no block detected
        """
        # Handle case where all inputs are None
        if response is None and exception is None and html_content is None:
            return None
        
        # Check exception-based blocks first
        if exception:
            if isinstance(exception, Timeout):
                return BlockType.TIMEOUT
            if isinstance(exception, RequestsConnectionError):
                return BlockType.CONNECTION_ERROR
        
        # Check response status codes
        if response:
            status_code = response.status_code
            
            # Rate limiting
            if status_code == 429:
                return BlockType.RATE_LIMIT
            
            # Forbidden
            if status_code == 403:
                return BlockType.FORBIDDEN
            
            # Server errors (5xx)
            if 500 <= status_code < 600:
                return BlockType.SERVER_ERROR
            
            # Non-retryable client errors
            if status_code in [404, 410, 401, 400]:
                return BlockType.NON_RETRYABLE
        
        # Check HTML content for CAPTCHA and invalid content
        if html_content is not None:
            # Empty response
            if not html_content.strip():
                return BlockType.INVALID_HTML
            
            # CAPTCHA detection (case-insensitive)
            html_lower = html_content.lower()
            for pattern in BlockDetector.CAPTCHA_PATTERNS:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    return BlockType.CAPTCHA
        
        # No block detected
        return None
    
    @staticmethod
    def is_retryable(block_type: BlockType) -> bool:
        """Determine if block type should trigger retry.
        
        Args:
            block_type: Detected block type
            
        Returns:
            True if should retry, False otherwise
        """
        non_retryable = {BlockType.CAPTCHA, BlockType.NON_RETRYABLE}
        return block_type not in non_retryable
    
    @staticmethod
    def get_retry_strategy(block_type: BlockType) -> str:
        """Get recommended retry strategy for block type.
        
        Args:
            block_type: Detected block type
            
        Returns:
            Strategy name: "exponential" or "linear"
        """
        # Use linear backoff for transient network issues
        if block_type in {BlockType.TIMEOUT, BlockType.CONNECTION_ERROR}:
            return "linear"
        
        # Use exponential backoff for rate limiting and server errors
        return "exponential"
