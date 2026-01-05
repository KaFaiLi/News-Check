"""Configuration settings for the News Scraper application."""
import os 

# Azure OpenAI API settings
OPENAI_API_KEY = os.environ['AZURE_OPENAI_API_KEY']
OPENAI_API_BASE = os.environ['AZURE_OPENAI_API_BASE']
AZURE_DEPLOYMENT_NAME = 'gpt-4.1-nano'
AZURE_API_VERSION = '2024-02-01'

# Content Analysis settings
USE_LLM = True  # Set to True to use the LLM for content analysis, False for keyword-only mode
LLM_THRESHOLD = 0.1  # Minimum keyword relevance score to trigger LLM analysis

# RSS Feed settings
MAX_RETRIES = 5  # Maximum number of retry attempts for failed requests
INITIAL_DELAY = 1  # Initial delay between requests in seconds

# Request settings
REQUEST_TIMEOUT = 30  # Request timeout in seconds
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Retry settings (Enhanced Scraper Resilience)
MAX_RETRY_ATTEMPTS = 5  # Maximum number of retry attempts for blocked requests
INITIAL_BACKOFF_DELAY = 1  # Initial delay in seconds for exponential backoff
MAX_BACKOFF_DELAY = 60  # Maximum delay in seconds for exponential backoff (capped)
RANDOM_DELAY_RANGE = (1, 5)  # Random delay range in seconds between requests (min, max)
RETRY_ON_STATUS_CODES = [429, 403, 500, 502, 503, 504]  # HTTP status codes that trigger retry

# Degradation settings (Graceful Degradation under sustained blocking)
ENABLE_GRACEFUL_DEGRADATION = True  # Enable partial results collection when blocking occurs
MIN_SUCCESS_THRESHOLD = 0.6  # Minimum success rate to avoid degraded mode (60%)
MAX_CONSECUTIVE_FAILURES = 3  # Maximum consecutive failures before entering degraded mode
DEGRADED_MODE_RETRY_LIMIT = 2  # Reduced retry attempts when in degraded mode
COLLECT_PARTIAL_RESULTS = True  # Whether to collect and return partial results on failure
INCLUDE_DEGRADATION_WARNING = True  # Add warnings to reports when operating in degraded mode

# User Agent Pool for rotation
USER_AGENT_POOL = [
    # Chrome 120 (2 variants for distribution)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Edge 120
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    # Firefox 121
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    # Safari 17 (emulated on Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
]

# Output settings
OUTPUT_DIR = 'Output'  # Directory for saving scraped results

# Validation: Ensure retry configuration values are valid
if not isinstance(MAX_RETRY_ATTEMPTS, int) or MAX_RETRY_ATTEMPTS <= 0:
    raise ValueError(f"MAX_RETRY_ATTEMPTS must be a positive integer, got: {MAX_RETRY_ATTEMPTS}")

if not isinstance(INITIAL_BACKOFF_DELAY, (int, float)) or INITIAL_BACKOFF_DELAY <= 0:
    raise ValueError(f"INITIAL_BACKOFF_DELAY must be a positive number, got: {INITIAL_BACKOFF_DELAY}")

if not isinstance(MAX_BACKOFF_DELAY, (int, float)) or MAX_BACKOFF_DELAY <= 0:
    raise ValueError(f"MAX_BACKOFF_DELAY must be a positive number, got: {MAX_BACKOFF_DELAY}")

if not isinstance(RANDOM_DELAY_RANGE, tuple) or len(RANDOM_DELAY_RANGE) != 2:
    raise ValueError(f"RANDOM_DELAY_RANGE must be a tuple of (min, max), got: {RANDOM_DELAY_RANGE}")

if RANDOM_DELAY_RANGE[0] < 0 or RANDOM_DELAY_RANGE[1] < RANDOM_DELAY_RANGE[0]:
    raise ValueError(f"RANDOM_DELAY_RANGE must have non-negative values with max >= min, got: {RANDOM_DELAY_RANGE}")

if not USER_AGENT_POOL:
    raise ValueError("USER_AGENT_POOL cannot be empty")

# Validation: Ensure degradation configuration values are valid
if not isinstance(MIN_SUCCESS_THRESHOLD, (int, float)) or not (0 < MIN_SUCCESS_THRESHOLD <= 1):
    raise ValueError(f"MIN_SUCCESS_THRESHOLD must be between 0 and 1, got: {MIN_SUCCESS_THRESHOLD}")

if not isinstance(MAX_CONSECUTIVE_FAILURES, int) or MAX_CONSECUTIVE_FAILURES < 1:
    raise ValueError(f"MAX_CONSECUTIVE_FAILURES must be a positive integer, got: {MAX_CONSECUTIVE_FAILURES}")

if not isinstance(DEGRADED_MODE_RETRY_LIMIT, int) or DEGRADED_MODE_RETRY_LIMIT < 0:
    raise ValueError(f"DEGRADED_MODE_RETRY_LIMIT must be a non-negative integer, got: {DEGRADED_MODE_RETRY_LIMIT}")