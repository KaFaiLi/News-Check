"""Pydantic models for structured output parsing and data validation.

This module defines all data models used throughout the News-Check application,
including retry tracking, degradation status, block types, and LLM output schemas.
All models use Pydantic for validation and type safety.

Model Categories:
    1. Retry & Blocking Models:
       - BlockType: Enum of blocking response types
       - DegradationStatus: Tracks graceful degradation state
       - RetryMetadata: Retry attempt metadata
       - RetryEvent: Individual retry event log entry

    2. Content Analysis Models:
       - ArticleAnalysis: LLM-generated article insights
       - TrendAnalysis: Multi-article trend analysis

    3. Document Generation Models:
       - BriefSummary: Brief article summary format
       - DetailedReport: Detailed report with full analysis

Key Features:
    - Type-safe data validation with Pydantic
    - JSON schema generation for documentation
    - Examples embedded in model configs
    - Helper methods for status tracking (DegradationStatus)

Typical Usage:
    from src.models import DegradationStatus, RetryEvent, BlockType

    # Track degradation
    status = DegradationStatus()
    status.update_failure("Fetch failed")
    if status.check_degradation_threshold(0.6, 3):
        print("System degraded")

    # Create retry event
    event = RetryEvent(
        timestamp=datetime.now().isoformat(),
        url="https://example.com",
        outcome="retry_scheduled"
    )
"""

from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

# Retry-related models (Enhanced Scraper Resilience)


class BlockType(str, Enum):
    """Types of blocking responses detected during scraping."""

    RATE_LIMIT = "rate_limit"  # HTTP 429
    FORBIDDEN = "forbidden"  # HTTP 403
    CAPTCHA = "captcha"  # CAPTCHA page detected
    TIMEOUT = "timeout"  # Request or connection timeout
    CONNECTION_ERROR = "connection_error"  # Network connection failed
    SERVER_ERROR = "server_error"  # HTTP 5xx errors
    INVALID_HTML = "invalid_html"  # Malformed or empty response
    NON_RETRYABLE = "non_retryable"  # 404, 410, 401, etc.
    SOFT_BLOCK = "soft_block"  # Consent walls, JS required, bot pages


class DegradationStatus(BaseModel):
    """Status of graceful degradation during scraping."""

    is_degraded: bool = False  # Whether system is in degraded mode
    total_attempts: int = 0  # Total scraping attempts
    successful_attempts: int = 0  # Successful attempts
    failed_attempts: int = 0  # Failed attempts
    consecutive_failures: int = 0  # Consecutive failures (triggers degraded mode)
    success_rate: float = 1.0  # Success rate (successful/total)
    collected_results_count: int = 0  # Number of partial results collected
    warnings: List[str] = []  # Degradation warnings for report generation

    def update_success(self):
        """Update status after successful attempt."""
        self.total_attempts += 1
        self.successful_attempts += 1
        self.consecutive_failures = 0
        self.success_rate = (
            self.successful_attempts / self.total_attempts
            if self.total_attempts > 0
            else 1.0
        )

    def update_failure(self, warning: Optional[str] = None):
        """Update status after failed attempt."""
        self.total_attempts += 1
        self.failed_attempts += 1
        self.consecutive_failures += 1
        self.success_rate = (
            self.successful_attempts / self.total_attempts
            if self.total_attempts > 0
            else 0.0
        )
        if warning:
            self.warnings.append(warning)

    def check_degradation_threshold(
        self, min_success_threshold: float, max_consecutive_failures: int
    ) -> bool:
        """Check if system should enter degraded mode."""
        # Enter degraded mode if success rate drops below threshold OR too many consecutive failures
        if (
            self.success_rate < min_success_threshold
            or self.consecutive_failures >= max_consecutive_failures
        ):
            self.is_degraded = True
            return True
        return False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "is_degraded": True,
                    "total_attempts": 10,
                    "successful_attempts": 5,
                    "failed_attempts": 5,
                    "consecutive_failures": 3,
                    "success_rate": 0.5,
                    "collected_results_count": 5,
                    "warnings": [
                        "Failed to fetch 5 articles due to blocking",
                        "Operating in degraded mode",
                    ],
                }
            ]
        }
    }


class RetryMetadata(BaseModel):
    """Metadata about a retry attempt."""

    attempt: int  # Current attempt number (1-indexed)
    max_attempts: int  # Maximum allowed attempts
    wait_time: float  # Time waited before this attempt (seconds)
    cumulative_wait: float  # Total time waited across all attempts (seconds)
    user_agent_rotated: bool  # Whether user agent was rotated for this attempt

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "attempt": 2,
                    "max_attempts": 5,
                    "wait_time": 2.0,
                    "cumulative_wait": 3.0,
                    "user_agent_rotated": True,
                }
            ]
        }
    }


class RetryEvent(BaseModel):
    """Log entry for a retry event."""

    timestamp: str  # ISO format timestamp
    url: Optional[str] = None  # URL being accessed
    keyword: Optional[str] = None  # Keyword being searched (if applicable)
    article_id: Optional[str] = None  # Article ID (if applicable)
    scraper_stage: Optional[str] = None  # Stage: "news_fetch", "content_fetch", etc.
    error_type: Optional[str] = None  # Exception type name
    error_message: Optional[str] = None  # Error message
    retry_metadata: Optional[RetryMetadata] = None  # Retry metadata
    outcome: str  # "retry_scheduled", "success", "permanent_failure"
    block_type: Optional[str] = None  # Block type if detected

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2026-01-05T10:30:45.123456",
                    "url": "https://example.com",
                    "keyword": "AI development",
                    "article_id": "article_123",
                    "scraper_stage": "content_fetch",
                    "error_type": "RequestException",
                    "error_message": "HTTP 429: Too Many Requests",
                    "retry_metadata": {
                        "attempt": 2,
                        "max_attempts": 5,
                        "wait_time": 2.0,
                        "cumulative_wait": 3.0,
                        "user_agent_rotated": True,
                    },
                    "outcome": "retry_scheduled",
                    "block_type": "rate_limit",
                }
            ]
        }
    }


# Original article analysis models


class ArticleAnalysis(BaseModel):
    """Model for individual article analysis."""

    relevance_score: float
    category: str
    impact_level: str
    key_points: List[str]
    industry_impact: str
    future_implications: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "relevance_score": 0.85,
                    "category": "AI Development",
                    "impact_level": "High",
                    "key_points": ["Key point 1", "Key point 2", "Key point 3"],
                    "industry_impact": "Significant impact on AI industry",
                    "future_implications": "Potential future developments",
                }
            ]
        }
    }


class TrendAnalysis(BaseModel):
    """Model for trend analysis of multiple articles."""

    key_trends: List[str]
    industry_developments: List[str]
    future_outlook: str
    category_insights: Dict[str, List[str]]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "key_trends": ["Trend 1", "Trend 2", "Trend 3"],
                    "industry_developments": ["Development 1", "Development 2"],
                    "future_outlook": "Positive outlook for the industry",
                    "category_insights": {
                        "AI Development": ["Insight 1", "Insight 2"],
                        "Fintech": ["Insight 1", "Insight 2"],
                        "GenAI Usage": ["Insight 1", "Insight 2"],
                    },
                }
            ]
        }
    }


class BriefSummary(BaseModel):
    """Model for brief article summary."""

    title: str
    summary: str
    significance: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Article Title",
                    "summary": "Brief summary of the article",
                    "significance": "Why this article matters",
                    "image_url": "https://example.com/image.jpg",
                }
            ]
        }
    }


class DetailedReport(BaseModel):
    """Model for detailed article report."""

    title: str
    category: str
    analysis: ArticleAnalysis
    summary: str
    source_info: Dict[str, str]
    metadata: Dict[str, str]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Article Title",
                    "category": "AI Development",
                    "analysis": {
                        "relevance_score": 0.85,
                        "category": "AI Development",
                        "impact_level": "High",
                        "key_points": ["Point 1", "Point 2"],
                        "industry_impact": "Major impact",
                        "future_implications": "Future implications",
                    },
                    "summary": "Detailed summary",
                    "source_info": {"url": "https://example.com", "date": "2024-03-25"},
                    "metadata": {"author": "John Doe", "publisher": "Tech News"},
                }
            ]
        }
    }
