"""Configuration settings for the News Scraper application."""

import os

# Azure OpenAI API settings
OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
OPENAI_API_BASE = os.environ["AZURE_OPENAI_API_BASE"]
AZURE_DEPLOYMENT_NAME = "gpt-4.1-nano"
AZURE_API_VERSION = "2024-02-01"

# Content Analysis settings
USE_LLM = (
    True  # Set to True to use the LLM for content analysis, False for keyword-only mode
)
LLM_THRESHOLD = 0.1  # Minimum keyword relevance score to trigger LLM analysis

# RSS Feed settings
MAX_RETRIES = 5  # Maximum number of retry attempts for failed requests
INITIAL_DELAY = 1  # Initial delay between requests in seconds

# Request settings
REQUEST_TIMEOUT = 30  # Request timeout in seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Retry settings (Enhanced Scraper Resilience)
MAX_RETRY_ATTEMPTS = 5  # Maximum number of retry attempts for blocked requests
INITIAL_BACKOFF_DELAY = 1  # Initial delay in seconds for exponential backoff
MAX_BACKOFF_DELAY = 60  # Maximum delay in seconds for exponential backoff (capped)
RANDOM_DELAY_RANGE = (1, 5)  # Random delay range in seconds between requests (min, max)
RETRY_ON_STATUS_CODES = [
    429,
    403,
    500,
    502,
    503,
    504,
]  # HTTP status codes that trigger retry

# Degradation settings (Graceful Degradation under sustained blocking)
ENABLE_GRACEFUL_DEGRADATION = (
    True  # Enable partial results collection when blocking occurs
)
MIN_SUCCESS_THRESHOLD = 0.6  # Minimum success rate to avoid degraded mode (60%)
MAX_CONSECUTIVE_FAILURES = (
    3  # Maximum consecutive failures before entering degraded mode
)
DEGRADED_MODE_RETRY_LIMIT = 2  # Reduced retry attempts when in degraded mode
COLLECT_PARTIAL_RESULTS = (
    True  # Whether to collect and return partial results on failure
)
INCLUDE_DEGRADATION_WARNING = (
    True  # Add warnings to reports when operating in degraded mode
)

# User Agent Pool for rotation
USER_AGENT_POOL = [
    # Chrome 120 (2 variants for distribution)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Edge 120
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Firefox 121
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari 17 (emulated on Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

# Output settings
OUTPUT_DIR = "Output"  # Directory for saving scraped results

# Validation: Ensure retry configuration values are valid
if not isinstance(MAX_RETRY_ATTEMPTS, int) or MAX_RETRY_ATTEMPTS <= 0:
    raise ValueError(
        f"MAX_RETRY_ATTEMPTS must be a positive integer, got: {MAX_RETRY_ATTEMPTS}"
    )

if not isinstance(INITIAL_BACKOFF_DELAY, (int, float)) or INITIAL_BACKOFF_DELAY <= 0:
    raise ValueError(
        f"INITIAL_BACKOFF_DELAY must be a positive number, got: {INITIAL_BACKOFF_DELAY}"
    )

if not isinstance(MAX_BACKOFF_DELAY, (int, float)) or MAX_BACKOFF_DELAY <= 0:
    raise ValueError(
        f"MAX_BACKOFF_DELAY must be a positive number, got: {MAX_BACKOFF_DELAY}"
    )

if not isinstance(RANDOM_DELAY_RANGE, tuple) or len(RANDOM_DELAY_RANGE) != 2:
    raise ValueError(
        f"RANDOM_DELAY_RANGE must be a tuple of (min, max), got: {RANDOM_DELAY_RANGE}"
    )

if RANDOM_DELAY_RANGE[0] < 0 or RANDOM_DELAY_RANGE[1] < RANDOM_DELAY_RANGE[0]:
    raise ValueError(
        f"RANDOM_DELAY_RANGE must have non-negative values with max >= min, got: {RANDOM_DELAY_RANGE}"
    )

if not USER_AGENT_POOL:
    raise ValueError("USER_AGENT_POOL cannot be empty")

# Validation: Ensure degradation configuration values are valid
if not isinstance(MIN_SUCCESS_THRESHOLD, (int, float)) or not (
    0 < MIN_SUCCESS_THRESHOLD <= 1
):
    raise ValueError(
        f"MIN_SUCCESS_THRESHOLD must be between 0 and 1, got: {MIN_SUCCESS_THRESHOLD}"
    )

if not isinstance(MAX_CONSECUTIVE_FAILURES, int) or MAX_CONSECUTIVE_FAILURES < 1:
    raise ValueError(
        f"MAX_CONSECUTIVE_FAILURES must be a positive integer, got: {MAX_CONSECUTIVE_FAILURES}"
    )

if not isinstance(DEGRADED_MODE_RETRY_LIMIT, int) or DEGRADED_MODE_RETRY_LIMIT < 0:
    raise ValueError(
        f"DEGRADED_MODE_RETRY_LIMIT must be a non-negative integer, got: {DEGRADED_MODE_RETRY_LIMIT}"
    )

# ============================================================================
# SOURCE RELIABILITY SCORING CONFIGURATION
# ============================================================================
"""
Source Reliability Scoring System

This configuration defines a 3-tier credibility system for news sources:
- Tier 1: Premium international news organizations (CNN, BBC, NYT, etc.)
- Tier 2: Established news and industry outlets (TechCrunch, Forbes, etc.)
- Tier 3: Unranked/unknown sources (default for sources not in tier-1 or tier-2)

HOW TO ADD A NEW SOURCE:
1. Determine the appropriate tier based on editorial standards and reputation
2. Add the base domain (e.g., 'economist.com') to the appropriate tier list
3. Subdomain matching is automatic (e.g., 'economist.com' matches 'www.economist.com')
4. No code changes needed - configuration takes effect immediately

HOW TO MODIFY SCORING WEIGHTS:
1. Adjust SCORE_WEIGHT_* values to change the importance of each factor
2. Ensure all weights sum to 1.0 (validation enforced on startup)
3. Default: 50% keyword relevance, 30% trending, 20% source reliability

EXAMPLE CONFIGURATIONS:
- More emphasis on source: KEYWORD=0.4, TRENDING=0.3, SOURCE=0.3
- Keyword-focused: KEYWORD=0.7, TRENDING=0.2, SOURCE=0.1
"""

# Tier 1: Premium international news sources
# These sources receive the highest reliability multiplier (1.3x)
SOURCE_RELIABILITY_TIER_1 = [
    "cnn.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "wsj.com",
    "reuters.com",
    "apnews.com",
    "ap.org",
    "bloomberg.com",
    "ft.com",
    "theguardian.com",
    "washingtonpost.com",
]

# Tier 2: Established news and industry outlets
# These sources receive a moderate reliability multiplier (1.1x)
SOURCE_RELIABILITY_TIER_2 = [
    "techcrunch.com",
    "politico.com",
    "thehill.com",
    "businessinsider.com",
    "forbes.com",
    "axios.com",
    "theverge.com",
    "cnbc.com",
    "npr.org",
    "time.com",
]

# Tier multipliers (tier-3 defaults to 1.0 for unlisted sources)
# Higher multiplier = higher source score in final ranking
TIER_1_MULTIPLIER = 1.3  # Premium sources (30% boost)
TIER_2_MULTIPLIER = 1.1  # Established sources (10% boost)
TIER_3_MULTIPLIER = 1.0  # Unknown sources (no boost)

# Score combination weights (must sum to 1.0)
# These weights determine how much each factor contributes to the overall article score
SCORE_WEIGHT_KEYWORD = 0.5  # 50% - Keyword relevance to target categories
SCORE_WEIGHT_TRENDING = 0.3  # 30% - Trending score (frequency, recency, diversity)
SCORE_WEIGHT_SOURCE = 0.2  # 20% - Source reliability tier

# High relevance score (title/snippet only) component weights
# These weights are normalized for blending the relevance_score only.
RELEVANCE_KEYWORD_DENSITY_WEIGHT = 0.7
RELEVANCE_RECENCY_WEIGHT = 0.2
RELEVANCE_SOURCE_WEIGHT = 0.0
RELEVANCE_DUPLICATE_PENALTY_WEIGHT = 0.1

# Content extraction thresholds
MIN_EXTRACTED_TEXT_LENGTH = 600
MIN_EXTRACTED_PARAGRAPHS = 3

# Source diversity cap
# Maximum number of articles from the same source in top results
# Prevents any single source from dominating the final selection
MAX_ARTICLES_PER_SOURCE = 3

# Markdown conversion settings
# Maximum length of markdown content sent to LLM (in characters)
# Articles longer than this are truncated to prevent token overflow
MAX_MARKDOWN_LENGTH = 400000  # 400K characters (~100K tokens)
TRUNCATION_INDICATOR = "\n\n[Content truncated at 400,000 characters]"

# Validation: Ensure source reliability configuration values are valid


def validate_source_reliability_config():
    """
    Validate source reliability configuration on startup.

    Checks performed:
    1. Tier lists are of correct type (list) and contain strings
    2. Score weights sum to 1.0 (within 0.001 tolerance)
    3. All multipliers are positive numbers
    4. MAX_ARTICLES_PER_SOURCE is a positive integer
    5. MAX_MARKDOWN_LENGTH is a positive integer
    6. No duplicate domains across tiers

    Raises:
        ValueError: If any validation check fails, with descriptive error message

    Returns:
        bool: True if all validations pass
    """
    # Check tier-1 list type and content
    if not isinstance(SOURCE_RELIABILITY_TIER_1, list) or not all(
        isinstance(d, str) for d in SOURCE_RELIABILITY_TIER_1
    ):
        raise ValueError("SOURCE_RELIABILITY_TIER_1 must be a list of domain strings")

    # Check tier-2 list type and content
    if not isinstance(SOURCE_RELIABILITY_TIER_2, list) or not all(
        isinstance(d, str) for d in SOURCE_RELIABILITY_TIER_2
    ):
        raise ValueError("SOURCE_RELIABILITY_TIER_2 must be a list of domain strings")

    # Check for duplicate domains across tiers
    tier1_set = set(SOURCE_RELIABILITY_TIER_1)
    tier2_set = set(SOURCE_RELIABILITY_TIER_2)
    overlap = tier1_set.intersection(tier2_set)
    if overlap:
        raise ValueError(
            f"Duplicate domains found in both tier-1 and tier-2: {overlap}"
        )

    # Check tier multipliers are positive numbers
    if not isinstance(TIER_1_MULTIPLIER, (int, float)) or TIER_1_MULTIPLIER <= 0:
        raise ValueError(
            f"TIER_1_MULTIPLIER must be a positive number, got: {TIER_1_MULTIPLIER}"
        )

    if not isinstance(TIER_2_MULTIPLIER, (int, float)) or TIER_2_MULTIPLIER <= 0:
        raise ValueError(
            f"TIER_2_MULTIPLIER must be a positive number, got: {TIER_2_MULTIPLIER}"
        )

    if not isinstance(TIER_3_MULTIPLIER, (int, float)) or TIER_3_MULTIPLIER <= 0:
        raise ValueError(
            f"TIER_3_MULTIPLIER must be a positive number, got: {TIER_3_MULTIPLIER}"
        )

    # Validate score weights sum to 1.0 (with floating point tolerance)
    weight_sum = SCORE_WEIGHT_KEYWORD + SCORE_WEIGHT_TRENDING + SCORE_WEIGHT_SOURCE
    if abs(weight_sum - 1.0) > 0.001:
        raise ValueError(f"Score weights must sum to 1.0, got: {weight_sum}")

    # Check diversity cap is a positive integer
    if not isinstance(MAX_ARTICLES_PER_SOURCE, int) or MAX_ARTICLES_PER_SOURCE < 1:
        raise ValueError(
            f"MAX_ARTICLES_PER_SOURCE must be a positive integer, got: {MAX_ARTICLES_PER_SOURCE}"
        )

    # Check markdown length limit is a positive integer
    if not isinstance(MAX_MARKDOWN_LENGTH, int) or MAX_MARKDOWN_LENGTH <= 0:
        raise ValueError(
            f"MAX_MARKDOWN_LENGTH must be a positive integer, got: {MAX_MARKDOWN_LENGTH}"
        )

    relevance_weight_sum = (
        RELEVANCE_KEYWORD_DENSITY_WEIGHT
        + RELEVANCE_RECENCY_WEIGHT
        + RELEVANCE_SOURCE_WEIGHT
        + RELEVANCE_DUPLICATE_PENALTY_WEIGHT
    )
    if abs(relevance_weight_sum - 1.0) > 0.001:
        raise ValueError(
            f"Relevance weights must sum to 1.0, got: {relevance_weight_sum}"
        )

    if not isinstance(MIN_EXTRACTED_TEXT_LENGTH, int) or MIN_EXTRACTED_TEXT_LENGTH <= 0:
        raise ValueError(
            f"MIN_EXTRACTED_TEXT_LENGTH must be a positive integer, got: {MIN_EXTRACTED_TEXT_LENGTH}"
        )

    if not isinstance(MIN_EXTRACTED_PARAGRAPHS, int) or MIN_EXTRACTED_PARAGRAPHS <= 0:
        raise ValueError(
            f"MIN_EXTRACTED_PARAGRAPHS must be a positive integer, got: {MIN_EXTRACTED_PARAGRAPHS}"
        )

    return True


# Run validation on module import
validate_source_reliability_config()
