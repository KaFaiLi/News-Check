# Anti-Blocking Features Guide

## Overview

The News-Check scraper includes comprehensive anti-blocking mechanisms to ensure reliable daily news collection even when facing rate limits, CAPTCHAs, or temporary blocks from Google News and article sources.

## Key Features

### 1. Intelligent Block Detection

The system automatically detects and classifies blocking responses:

- **HTTP Status Codes**: 429 (rate limit), 403 (forbidden), 5xx (server errors)
- **CAPTCHA Detection**: Pattern matching in HTML content
- **Network Errors**: Timeouts, connection failures
- **Invalid Responses**: Empty or malformed HTML

### 2. Exponential Backoff Retry

Automatic retry with increasing delays:

```python
Attempt 1: Wait 1s
Attempt 2: Wait 2s
Attempt 3: Wait 4s
Attempt 4: Wait 8s
Attempt 5: Wait 16s (capped at 60s)
```

- **Max Attempts**: 5 (configurable)
- **Backoff Strategy**: Exponential with jitter
- **Max Delay**: 60 seconds

### 3. User Agent Rotation

Rotates through legitimate browser user agents:

- Chrome 120, 121
- Edge 120
- Firefox 121
- Safari 17

Rotation happens automatically on 403/429 responses to avoid fingerprinting.

### 4. Graceful Degradation

When sustained blocking occurs, the system:

1. **Monitors Success Rate**: Tracks successful vs failed attempts
2. **Enters Degraded Mode**: When success rate drops below 60% OR 3+ consecutive failures
3. **Collects Partial Results**: Returns what was successfully fetched
4. **Warns Users**: Adds visible warnings to all reports

### 5. Comprehensive Logging

All retry events are logged to JSON files:

**Location**: `Output/retry_logs/{session_id}_retry_log.json`

**Contents**:
- Timestamp of each retry attempt
- URL and error details
- Block type detected
- Wait times and cumulative delays
- User agent rotation events
- Degradation status

## Configuration

Edit `src/config.py` to customize anti-blocking behavior:

### Retry Settings

```python
# Maximum retry attempts
MAX_RETRY_ATTEMPTS = 5

# Exponential backoff delays (seconds)
INITIAL_BACKOFF_DELAY = 1
MAX_BACKOFF_DELAY = 60

# Random delay between requests (min, max)
RANDOM_DELAY_RANGE = (1, 5)

# HTTP status codes that trigger retry
RETRY_ON_STATUS_CODES = [429, 403, 500, 502, 503, 504]
```

### Degradation Settings

```python
# Enable graceful degradation
ENABLE_GRACEFUL_DEGRADATION = True

# Minimum success rate before degrading (60%)
MIN_SUCCESS_THRESHOLD = 0.6

# Max consecutive failures before degrading
MAX_CONSECUTIVE_FAILURES = 3

# Reduced retry attempts in degraded mode
DEGRADED_MODE_RETRY_LIMIT = 2

# Collect partial results on failure
COLLECT_PARTIAL_RESULTS = True

# Include degradation warnings in reports
INCLUDE_DEGRADATION_WARNING = True
```

### User Agent Pool

```python
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
    # Add more user agents as needed
]
```

## Usage Examples

### Basic Usage (No Changes Required)

The anti-blocking features work automatically. Just run the scraper normally:

```python
from src.news_scraper_simple import GoogleNewsScraper

scraper = GoogleNewsScraper(max_articles_per_keyword=100)
df = scraper.get_news(
    keywords=['artificial intelligence', 'fintech'],
    start_date='2026-01-01',
    end_date='2026-01-05'
)
```

### Checking Degradation Status

```python
scraper = GoogleNewsScraper(max_articles_per_keyword=100)
df = scraper.get_news(keywords=['AI'], start_date='2026-01-01', end_date='2026-01-05')

# Check if system degraded
if scraper.degradation_status.is_degraded:
    print(f"⚠️ System degraded!")
    print(f"Success rate: {scraper.degradation_status.success_rate:.1%}")
    print(f"Failures: {scraper.degradation_status.failed_attempts}")
    print(f"Warnings: {scraper.degradation_status.warnings}")
```

### Accessing Retry Logs

```python
from src.retry_logger import retry_logger

# Get session summary
summary = retry_logger.get_session_summary()
print(f"Total retries: {summary['total_retries']}")
print(f"Success count: {summary['success_count']}")
print(f"Average wait: {summary['avg_wait_time']}s")

# Log file path
print(f"Logs: {retry_logger.log_file}")
```

### Custom Retry Decorator

Apply retry logic to your own functions:

```python
from src.retry_policy import retry_with_backoff
import requests

@retry_with_backoff(
    max_attempts=5,
    backoff_strategy="exponential",
    retry_on=(requests.exceptions.RequestException,)
)
def fetch_custom_data(url):
    response = requests.get(url)
    return response.json()
```

## Monitoring & Debugging

### Console Output

The scraper provides real-time feedback:

```
✓ HTML fetched successfully
⚠️ Block type: rate_limit. Retrying (2/5) after 2.0s...
⚠️ Entering degraded mode: 3 consecutive failures
⚠️ Collecting partial results: 47 articles retrieved so far
```

### Log Files

Check retry logs for detailed analysis:

```bash
# View latest retry log
cat Output/retry_logs/$(ls -t Output/retry_logs | head -1)
```

### Report Warnings

Degradation warnings appear in all generated documents:

- **Word Documents**: Yellow warning box with degradation stats
- **HTML Emails**: Alert banner with success rate and failure count
- **Console Output**: Emoji indicators and detailed status

## Troubleshooting

### High Failure Rate

If experiencing many blocks:

1. **Increase delays**: Adjust `RANDOM_DELAY_RANGE` to (2, 8)
2. **Reduce volume**: Lower `max_articles_per_keyword`
3. **Check user agents**: Ensure `USER_AGENT_POOL` has current browser versions
4. **Review logs**: Check `retry_logs/` for patterns

### CAPTCHA Detection

If hitting CAPTCHAs frequently:

- System will mark as non-retryable and skip
- Consider using alternative news sources
- Reduce scraping frequency (run daily instead of hourly)

### Degraded Mode Activation

Normal behavior when:
- Google News is rate limiting
- Network connectivity issues
- High volume scraping

System will:
- Collect partial results
- Add warnings to reports
- Log degradation event

## Best Practices

1. **Monitor Logs**: Regularly check retry logs for patterns
2. **Adjust Thresholds**: Tune degradation thresholds based on your reliability needs
3. **Stagger Runs**: Avoid running scraper at the same time each day
4. **Respect Limits**: Keep `max_articles_per_keyword` reasonable (≤100)
5. **Update User Agents**: Periodically refresh `USER_AGENT_POOL` with current browser versions

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     News Scraper Request                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              @retry_with_backoff Decorator                   │
│  • Detects blocks (BlockDetector)                            │
│  • Rotates user agents (UserAgentPool)                       │
│  • Logs events (RetryLogger)                                 │
│  • Tracks degradation (DegradationStatus)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│  Success: Log   │        │ Failure: Retry  │
│  & Continue     │        │ with Backoff    │
└─────────────────┘        └────────┬────────┘
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                          ▼                   ▼
                   ┌──────────────┐   ┌──────────────┐
                   │  Retryable   │   │Non-Retryable │
                   │  (Retry)     │   │  (Fail)      │
                   └──────────────┘   └──────────────┘
                          │
                          ▼
                   ┌──────────────────┐
                   │ Degradation      │
                   │ Check            │
                   └────────┬─────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │ Normal Mode  │        │ Degraded Mode│
        │ Continue     │        │ Partial Results│
        └──────────────┘        └──────────────┘
```

## Version History

- **v1.0** (2026-01-05): Initial anti-blocking implementation
  - Exponential backoff retry
  - User agent rotation
  - Block detection and classification
  - Comprehensive event logging
  - Graceful degradation
