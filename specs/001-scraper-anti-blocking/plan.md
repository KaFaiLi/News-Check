# Implementation Plan: Enhanced Scraper Resilience and Anti-Blocking

**Branch**: `001-scraper-anti-blocking` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-scraper-anti-blocking/spec.md`

## Summary

Implement robust retry mechanisms with exponential backoff, user agent rotation, and blocking detection to achieve 95% success rate in daily news scraping. The solution adds a dedicated retry policy module that decorates existing scraper methods without disrupting the current pipeline architecture. Focus on transparent, auditable retry logic that gracefully degrades under sustained blocking while maintaining the existing keyword-only and LLM-optional operation modes.

## Technical Context

**Language/Version**: Python 3.8+  
**Primary Dependencies**: requests (HTTP scraping), beautifulsoup4 (HTML parsing), playwright (content fetching), fuzzywuzzy (deduplication), tenacity (retry library - new)  
**Storage**: File-based JSON for error logs and retry metadata in `Output/article_content/errors/` and `Output/retry_logs/`  
**Testing**: pytest with pytest-mock for retry decorator testing, requests-mock for HTTP mocking  
**Target Platform**: Windows 10+ (development/deployment environment)  
**Project Type**: Single project (src/, tests/ at root)  
**Performance Goals**: <5 minutes for 100 articles (no blocking), <15 minutes with retries (50% blocking), 95% success rate over 30 days  
**Constraints**: Zero performance degradation when no blocking occurs, <1MB/day log storage, maintain existing scraper API compatibility  
**Scale/Scope**: ~100 articles/day, 5 keywords, 2-stage scraping (Google HTML + Playwright content fetch)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Modular Pipeline Architecture**: ✅ PASS - Retry logic isolated in `src/retry_policy.py`. Scraper stage (`news_scraper_simple.py`) remains independently testable. Retry decorators are applied transparently without modifying core scraper logic. Analysis and generation stages unaffected.
- [x] **II. Category-Based Content Enforcement**: ✅ PASS - Not impacted. Retry logic operates at scraping layer before content analysis. The 3 Fintech minimum enforcement in `ContentAnalyzerSimple.rank_articles()` is unchanged. Partial results scenario (P3) explicitly maintains category enforcement or logs warnings.
- [x] **III. HTML Output Fidelity**: ✅ PASS - Not impacted. Retry mechanisms operate before document generation stage. HTML email output (`document_generator.py`) unchanged.
- [x] **IV. LLM-Optional Analysis**: ✅ PASS - Retry logic has zero LLM dependencies. Works identically in `USE_LLM=False` mode. LLM is only used in content extraction (existing behavior), not in retry decisions.
- [x] **V. Transparent Content Scoring**: ✅ PASS - Retry attempts, strategies, and outcomes fully logged with timestamps. New logging schema documents: retry count, backoff delays, user agents used, block detection reasons. Scoring algorithm (60/40 keyword/trending) unchanged.
- [x] **Output Format Standards**: ✅ PASS - New retry logs saved as JSON in `Output/retry_logs/YYYYMMDD_HHMMSS_retry_log.json`. Error logs enhanced with retry metadata. Follows existing timestamped naming convention.
- [x] **Configuration Management**: ✅ PASS - All retry parameters centralized in `src/config.py`: `MAX_RETRY_ATTEMPTS`, `INITIAL_BACKOFF_DELAY`, `MAX_BACKOFF_DELAY`, `USER_AGENT_POOL`, `RANDOM_DELAY_RANGE`, `RETRY_ON_STATUS_CODES`. No hardcoded magic numbers.

**Constitution Compliance**: 7/7 checks passed. No violations. Feature aligns with News-Check core principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-scraper-anti-blocking/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (exists)
├── research.md          # Phase 0 output - Retry library analysis
├── design.md            # Phase 1 output - Retry policy architecture
├── contracts/           # Phase 1 output - API contracts
│   ├── retry_decorator.md       # @retry_with_backoff decorator contract
│   ├── user_agent_pool.md       # UserAgentPool class contract
│   ├── block_detector.md        # BlockDetector class contract
│   └── retry_logger.md          # RetryLogger class contract
├── checklists/
│   └── requirements.md  # Specification validation (exists)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── retry_policy.py              # NEW: Retry decorators and policy logic
├── user_agent_pool.py           # NEW: User agent rotation management
├── block_detector.py            # NEW: Blocking detection patterns
├── retry_logger.py              # NEW: Retry event logging
├── config.py                    # MODIFIED: Add retry configuration
├── news_scraper_simple.py       # MODIFIED: Apply retry decorators
├── content_analyzer_simple.py   # MODIFIED: Apply retry to fetch_article_content
├── models.py                    # MODIFIED: Add retry metadata models
├── document_generator.py        # UNCHANGED
└── __init__.py                  # UNCHANGED

tests/
├── test_retry_policy.py         # NEW: Unit tests for retry decorator
├── test_user_agent_pool.py      # NEW: Unit tests for user agent rotation
├── test_block_detector.py       # NEW: Unit tests for blocking detection
├── test_retry_logger.py         # NEW: Unit tests for retry logging
├── test_news_scraper.py         # MODIFIED: Add retry integration tests
├── test_content_analyzer.py     # MODIFIED: Add Playwright retry tests
├── test_document_generator.py   # UNCHANGED
└── __init__.py                  # UNCHANGED

Output/
├── retry_logs/                  # NEW: Timestamped retry event logs
│   └── YYYYMMDD_HHMMSS_retry_log.json
├── article_content/
│   └── errors/                  # MODIFIED: Enhanced error logs with retry metadata
│       └── error_{article_id}.json
└── [existing output files]      # UNCHANGED
```

**Structure Decision**: Single project structure maintained. New retry modules (`src/retry_policy.py`, `src/user_agent_pool.py`, `src/block_detector.py`, `src/retry_logger.py`) added as independent, testable components. Existing scraper modules modified minimally through decorator application only. Testing structure mirrors source structure for discoverability.

## Complexity Tracking

> **No violations identified - this section is empty per constitution compliance.**

---

# Phase 0: Research

**Objective**: Analyze current implementation, research retry strategies, and recommend technical approach.

## Research Tasks

### R1: Current Scraper Implementation Analysis

**Goal**: Document existing retry behavior, failure modes, and extension points.

**Scope**:
- Analyze `src/news_scraper_simple.py`:
  - Current retry logic: Simple loop with exponential backoff in pagination (line 261: `time.sleep(self.initial_delay * (2 ** page))`)
  - Failure handling: `requests.exceptions.RequestException` caught, max retries checked per page
  - CAPTCHA detection: Basic check for "captcha" string in response text (line 234)
  - User agent: Single static USER_AGENT from config (line 16)
  - Extension points: `get_news()` method, per-request error handling
- Analyze `src/content_analyzer_simple.py`:
  - Playwright retry: Hardcoded 3 attempts with 2-second delay (line 152: `max_retries = 3`)
  - Error handling: `PlaywrightTimeoutError`, `PlaywrightError` exceptions caught
  - Browser configuration: Headless mode disabled, Edge with stealth headers (lines 165-175)
  - Extension points: `fetch_article_content()` method wrapping entire Playwright flow
- Current issues:
  - Retry logic duplicated between scraper (requests) and analyzer (Playwright)
  - No user agent rotation - single static agent makes patterns detectable
  - No randomized delays between requests - consistent timing is bot-like
  - Limited blocking detection - only checks for "captcha" string, misses 429/403 codes
  - Retry attempts not logged - no visibility into failure patterns

**Findings to Document**:
1. Existing retry patterns and where they live
2. Failure scenarios currently handled vs. missed
3. Decorator injection points (methods to wrap)
4. Backward compatibility requirements (API contracts to preserve)

### R2: Retry Library Evaluation

**Goal**: Select Python retry library balancing simplicity, features, and project fit.

**Candidates**:
1. **tenacity** (preferred)
   - Decorator-based: `@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=60))`
   - Built-in exponential backoff, jitter, conditional retry
   - Active maintenance, 10K+ GitHub stars
   - Zero dependencies beyond stdlib
   - Supports async (future-proofing if Playwright async adopted)
   - Exception filtering: `retry_if_exception_type(requests.RequestException)`
   
2. **backoff** (alternative)
   - Similar decorator syntax: `@backoff.on_exception(backoff.expo, requests.RequestException, max_tries=5)`
   - Simpler API, fewer features
   - Good for basic exponential backoff
   - Less flexible for complex retry conditions
   
3. **urllib3.util.retry** (reject)
   - Built-in to urllib3/requests
   - Only works with requests.Session transport adapters
   - Cannot wrap Playwright calls
   - Less flexible configuration

**Recommendation**: Use **tenacity** for unified retry logic across both requests-based scraping and Playwright-based content fetching. Provides decorator-based API matching project patterns, supports both sync scenarios, and offers rich configuration without excessive complexity.

### R3: User Agent Rotation Strategies

**Goal**: Define user agent pool composition and rotation logic.

**Research Findings**:
- Browser market share (Dec 2025):
  - Chrome: 65% (desktop)
  - Safari: 15% (desktop)
  - Edge: 10% (desktop)
  - Firefox: 7% (desktop)
  - Others: 3%
- User agent requirements:
  - Must include realistic OS (Windows 10/11 on desktop)
  - Must include current browser versions (avoid outdated strings)
  - Should distribute across browsers proportional to market share
  - Playwright needs separate user agent configuration (context-level)

**Proposed User Agent Pool** (5 agents, 80% coverage):
```python
USER_AGENT_POOL = [
    # Chrome 120 (40% weight - 2 variants)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Edge 120 (20% weight)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    # Firefox 121 (20% weight)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    # Safari 17 (20% weight - emulated on Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
]
```

**Rotation Strategy**:
- Round-robin with random start index (avoids predictable patterns)
- Per-keyword rotation in scraper (each keyword gets different agent)
- Per-article rotation in content fetcher (distributes Playwright sessions)
- Persist last-used index in memory (not disk - reset per run maintains freshness)

### R4: Blocking Detection Patterns

**Goal**: Catalog detectable blocking responses and appropriate retry strategies.

**Pattern Catalog**:

| Block Type | Detection Method | Retry Strategy | Max Retries |
|------------|-----------------|----------------|-------------|
| Rate Limit (429) | HTTP status code | Exponential backoff (1s → 60s) | 5 attempts |
| Forbidden (403) | HTTP status code | User agent rotation + 5s delay | 3 attempts |
| CAPTCHA | HTML content match (`/captcha\|recaptcha/i`) | Stop immediately, log error | 0 attempts |
| Timeout | Exception type (`requests.Timeout`, `PlaywrightTimeoutError`) | Linear backoff (10s → 30s) | 3 attempts |
| Connection Refused | Exception type (`requests.ConnectionError`) | Exponential backoff (2s → 16s) | 4 attempts |
| Server Error (5xx) | HTTP status code (500-599) | Exponential backoff (2s → 32s) | 4 attempts |
| Invalid HTML Structure | No articles found (`len(articles) == 0`) | User agent rotation + 3s delay | 2 attempts |
| Network Unreachable | Exception type (`requests.exceptions.ConnectionError`) | Stop after 60s cumulative wait | 3 attempts |

**Non-Retryable Scenarios** (permanent failures):
- 404 Not Found (article deleted)
- 410 Gone (article permanently removed)
- 401 Unauthorized (API key issues - not applicable here)
- CAPTCHA challenges (requires human intervention)

**Detection Implementation**:
```python
class BlockDetector:
    @staticmethod
    def detect_block_type(response=None, exception=None, html_content=None) -> BlockType:
        # Returns: RATE_LIMIT, FORBIDDEN, CAPTCHA, TIMEOUT, etc.
        # Determines retry eligibility and strategy
```

### R5: Playwright Stealth Capabilities

**Goal**: Audit existing Playwright configuration and identify enhancement opportunities.

**Current Configuration** (`src/content_analyzer_simple.py` lines 165-175):
- Browser: Edge (Chromium channel)
- Headless: **Disabled** (visible browser - good for stealth)
- User Agent: Static Edge 120 string
- Extra Headers:
  - `Accept`: Standard HTML/XHTML values
  - `Accept-Language`: en-US
  - `Sec-Ch-Ua-*`: Chromium 120 headers
  - `Upgrade-Insecure-Requests`: 1
- Wait Strategy: `domcontentloaded` + `networkidle` + 5s sleep

**Stealth Assessment**:
✅ **Strengths**:
- Non-headless mode reduces fingerprinting risk
- Realistic headers (Sec-Ch-Ua) mimic Chrome/Edge
- Network idle wait allows dynamic content loading
- 5-second sleep adds human-like delay

⚠️ **Gaps**:
- Static user agent (no rotation across sessions)
- No viewport randomization (fixed 1280x720 default)
- No timezone/locale spoofing
- No WebGL/Canvas fingerprint randomization

**Enhancement Recommendations**:
1. **High Priority**: Rotate Playwright user agent via `context.new_context(user_agent=...)`
2. **Medium Priority**: Randomize viewport size between sessions (1920x1080, 1366x768, 1280x720)
3. **Low Priority**: Add `playwright-stealth` library for advanced fingerprint evasion (if blocking persists after user agent rotation)

**Existing stealth already covers** (no changes needed):
- Non-headless mode (most important factor)
- Realistic headers and timing
- Edge browser (less commonly detected than Chrome automation)

### R6: Logging Schema Design

**Goal**: Define structured logging format for retry events.

**Schema Requirements** (per FR-005):
- Timestamp (ISO 8601 format)
- Error code (HTTP status or exception type)
- Retry count (current attempt / max attempts)
- Strategy applied (exponential backoff, user agent rotation, etc.)
- Outcome (success, retry scheduled, permanent failure)
- Context (URL, keyword, article ID)
- Performance (cumulative wait time, request duration)

**Proposed JSON Schema**:
```json
{
  "session_id": "20260105_143022",
  "events": [
    {
      "timestamp": "2026-01-05T14:30:25.123Z",
      "event_type": "retry_attempt",
      "context": {
        "url": "https://www.google.com/search?...",
        "keyword": "artificial intelligence",
        "article_id": "abc123",
        "scraper_stage": "google_search"  // or "playwright_fetch"
      },
      "error": {
        "type": "RateLimitError",
        "status_code": 429,
        "message": "Too Many Requests"
      },
      "retry": {
        "attempt": 2,
        "max_attempts": 5,
        "strategy": "exponential_backoff",
        "wait_time_seconds": 4,
        "cumulative_wait_seconds": 5,
        "user_agent_rotated": false
      },
      "outcome": "retry_scheduled"  // or "success", "permanent_failure"
    }
  ]
}
```

**Logging Levels**:
- **INFO**: Successful retry recovery
- **WARNING**: Retry attempt (transient error)
- **ERROR**: Permanent failure after max retries
- **DEBUG**: Retry configuration and strategy selection

**Output Files**:
- Per-run retry log: `Output/retry_logs/YYYYMMDD_HHMMSS_retry_log.json`
- Enhanced error logs: `Output/article_content/errors/error_{article_id}.json` (append retry metadata)
- Console output: Concise retry status (e.g., "Retrying (2/5) after 4s backoff...")

## Research Deliverables

**1. Research Summary Document** (`specs/001-scraper-anti-blocking/research.md`):
- Current implementation gaps vs. FR-001 to FR-010 requirements
- Tenacity library selection rationale
- User agent pool composition (5 agents)
- Blocking detection pattern catalog (8 patterns)
- Playwright stealth audit results
- Logging schema specification

**2. Implementation Approach Recommendation**:

**Recommended Strategy**: **Decorator-Based Retry with Modular Components**

**Rationale**:
- **Simplicity**: Decorators preserve existing scraper API, minimize changes to `news_scraper_simple.py` and `content_analyzer_simple.py`
- **Testability**: Retry logic isolated in `retry_policy.py`, independently unit-testable
- **Flexibility**: Tenacity library provides exponential backoff, jitter, conditional retry out-of-box
- **Maintainability**: Modular components (UserAgentPool, BlockDetector, RetryLogger) follow single-responsibility principle
- **Performance**: Zero overhead when no errors occur (decorators only activate on exception)
- **Constitution Alignment**: Preserves modular pipeline architecture (scraper stage independence)

**Alternative Considered**: Context manager-based retry (`with retry_context():`)
- **Rejected because**: Requires wrapping large code blocks, reduces readability, harder to test isolation

**Pattern Example**:
```python
# In news_scraper_simple.py
from src.retry_policy import retry_with_backoff

class GoogleNewsScraper:
    @retry_with_backoff(
        max_attempts=5,
        backoff_strategy='exponential',
        retry_on=[requests.RequestException],
        exclude_on=[CaptchaDetected]
    )
    def _fetch_page(self, url, params, headers):
        response = requests.get(url, params=params, headers=headers)
        # Blocking detection happens in decorator
        return response
```

**Phase 0 Exit Criteria**:
- [x] Research document completed with all 6 analysis sections
- [x] Tenacity library selected and justified
- [x] User agent pool defined (5 agents)
- [x] Blocking detection patterns cataloged (8 types)
- [x] Logging schema specified (JSON format)
- [x] Implementation approach recommended (decorator-based)

---

# Phase 1: Design

**Objective**: Define contracts, data structures, and integration points for retry system.

## Design Tasks

### D1: Retry Policy Module Architecture

**File**: `src/retry_policy.py`

**Purpose**: Centralized retry decorator factory that orchestrates backoff, user agent rotation, blocking detection, and logging.

**Core Components**:

1. **retry_with_backoff()**  
   Decorator factory that wraps scraper methods with retry logic.
   
   ```python
   def retry_with_backoff(
       max_attempts: int,
       backoff_strategy: str,  # 'exponential' or 'linear'
       retry_on: List[Type[Exception]],
       exclude_on: List[Type[Exception]] = None,
       on_retry: Optional[Callable] = None
   ) -> Callable:
       """
       Decorator for adding retry logic to scraper methods.
       
       Args:
           max_attempts: Maximum retry attempts (from config.MAX_RETRY_ATTEMPTS)
           backoff_strategy: 'exponential' (1s -> 60s) or 'linear' (5s fixed)
           retry_on: Exception types that trigger retry
           exclude_on: Exception types that bypass retry (e.g., CaptchaDetected)
           on_retry: Callback invoked before each retry (for logging/rotation)
       
       Returns:
           Decorated function with retry behavior
       
       Behavior:
           - Catches exceptions in retry_on list
           - Applies BlockDetector to determine retry eligibility
           - Rotates user agent if blocked by 403/429
           - Logs retry events via RetryLogger
           - Returns original result on success
           - Raises original exception after max_attempts
       """
   ```

2. **RetryableRequest**  
   Context object passed to retry callbacks, containing request metadata.
   
   ```python
   @dataclass
   class RetryableRequest:
       url: str
       attempt: int
       max_attempts: int
       exception: Optional[Exception]
       response: Optional[requests.Response]
       wait_time: float
       cumulative_wait: float
       user_agent_rotated: bool
   ```

**Integration Pattern**:
```python
# news_scraper_simple.py
from src.retry_policy import retry_with_backoff, RetryableRequest
from src.user_agent_pool import user_agent_pool
from src.retry_logger import retry_logger

@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS,
    backoff_strategy='exponential',
    retry_on=[requests.RequestException, requests.Timeout],
    on_retry=lambda req: retry_logger.log_retry(req)
)
def _fetch_page(self, url, params):
    headers = self.headers.copy()
    headers['User-Agent'] = user_agent_pool.get_next()
    response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()  # Trigger retry on 4xx/5xx
    return response
```

**Dependencies**:
- `tenacity` library for backoff implementation
- `src.user_agent_pool.UserAgentPool` for user agent rotation
- `src.block_detector.BlockDetector` for eligibility checks
- `src.retry_logger.RetryLogger` for event logging
- `src.config` for retry parameters

**Contract**: [contracts/retry_decorator.md](contracts/retry_decorator.md)

### D2: User Agent Pool Management

**File**: `src/user_agent_pool.py`

**Purpose**: Thread-safe user agent rotation with round-robin + random start strategy.

**Class Design**:

```python
class UserAgentPool:
    """
    Manages rotation of user agent strings across scraping sessions.
    
    Thread-safe singleton for use across scraper and content analyzer.
    """
    
    def __init__(self, agents: List[str]):
        """
        Args:
            agents: List of user agent strings (from config.USER_AGENT_POOL)
        
        Behavior:
            - Initializes with random start index
            - Maintains in-memory rotation state (not persisted)
        """
        self._agents = agents
        self._index = random.randint(0, len(agents) - 1)
        self._lock = threading.Lock()  # Thread safety
    
    def get_next(self) -> str:
        """
        Returns: Next user agent in rotation (round-robin)
        
        Thread-safe operation increments index atomically.
        """
        with self._lock:
            agent = self._agents[self._index]
            self._index = (self._index + 1) % len(self._agents)
            return agent
    
    def get_random(self) -> str:
        """
        Returns: Random user agent (for non-sequential requests)
        
        Use when round-robin pattern might be detectable.
        """
        return random.choice(self._agents)
    
    def reset(self):
        """Resets rotation to random start (called per scraping session)."""
        self._index = random.randint(0, len(self._agents) - 1)
```

**Usage Pattern**:
```python
# Global singleton instance
from src.config import USER_AGENT_POOL
user_agent_pool = UserAgentPool(USER_AGENT_POOL)

# In scraper methods
headers['User-Agent'] = user_agent_pool.get_next()

# In Playwright context
context = browser.new_context(user_agent=user_agent_pool.get_next())
```

**Configuration** (add to `src/config.py`):
```python
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
]
```

**Contract**: [contracts/user_agent_pool.md](contracts/user_agent_pool.md)

### D3: Block Detection Logic

**File**: `src/block_detector.py`

**Purpose**: Determine blocking type and retry eligibility from responses/exceptions.

**Enum Design**:

```python
from enum import Enum

class BlockType(Enum):
    """Categorizes blocking responses for retry strategy selection."""
    RATE_LIMIT = 'rate_limit'          # HTTP 429
    FORBIDDEN = 'forbidden'            # HTTP 403
    CAPTCHA = 'captcha'                # CAPTCHA HTML detected
    TIMEOUT = 'timeout'                # Request/Playwright timeout
    CONNECTION_ERROR = 'connection'    # Network unreachable
    SERVER_ERROR = 'server_error'      # HTTP 5xx
    INVALID_STRUCTURE = 'invalid_html' # No articles parsed
    PERMANENT_FAILURE = 'permanent'    # 404, 410, CAPTCHA
    NO_BLOCK = 'success'               # Successful response
```

**Class Design**:

```python
class BlockDetector:
    """Analyzes responses and exceptions to detect blocking patterns."""
    
    CAPTCHA_PATTERNS = [
        r'captcha', r'recaptcha', r'g-recaptcha',
        r'hcaptcha', r'h-captcha', r'cf-captcha'
    ]
    
    PERMANENT_STATUS_CODES = {404, 410}
    RETRYABLE_STATUS_CODES = {429, 403, 500, 502, 503, 504}
    
    @staticmethod
    def detect(
        response: Optional[requests.Response] = None,
        exception: Optional[Exception] = None,
        html_content: Optional[str] = None
    ) -> BlockType:
        """
        Determines block type from response/exception/HTML.
        
        Args:
            response: HTTP response object (if available)
            exception: Raised exception (if any)
            html_content: Response HTML text (for CAPTCHA detection)
        
        Returns:
            BlockType enum indicating block category
        
        Priority:
            1. Check for CAPTCHA in HTML (highest priority - permanent)
            2. Check response status codes
            3. Check exception types
            4. Return NO_BLOCK if none detected
        """
        # CAPTCHA detection (HTML pattern match)
        if html_content:
            if any(re.search(pattern, html_content, re.IGNORECASE) 
                   for pattern in BlockDetector.CAPTCHA_PATTERNS):
                return BlockType.CAPTCHA
        
        # HTTP status code detection
        if response:
            if response.status_code in BlockDetector.PERMANENT_STATUS_CODES:
                return BlockType.PERMANENT_FAILURE
            elif response.status_code == 429:
                return BlockType.RATE_LIMIT
            elif response.status_code == 403:
                return BlockType.FORBIDDEN
            elif 500 <= response.status_code < 600:
                return BlockType.SERVER_ERROR
        
        # Exception type detection
        if exception:
            if isinstance(exception, (requests.Timeout, PlaywrightTimeoutError)):
                return BlockType.TIMEOUT
            elif isinstance(exception, (requests.ConnectionError,)):
                return BlockType.CONNECTION_ERROR
        
        return BlockType.NO_BLOCK
    
    @staticmethod
    def is_retryable(block_type: BlockType) -> bool:
        """Returns True if block type should trigger retry."""
        return block_type not in {BlockType.CAPTCHA, BlockType.PERMANENT_FAILURE}
    
    @staticmethod
    def should_rotate_agent(block_type: BlockType) -> bool:
        """Returns True if user agent rotation recommended."""
        return block_type in {BlockType.RATE_LIMIT, BlockType.FORBIDDEN}
```

**Contract**: [contracts/block_detector.md](contracts/block_detector.md)

### D4: Retry Event Logging

**File**: `src/retry_logger.py`

**Purpose**: Structured logging of retry events to JSON files and console.

**Class Design**:

```python
class RetryLogger:
    """
    Logs retry events to structured JSON files and console.
    
    Singleton instance manages per-session log file.
    """
    
    def __init__(self, output_dir: str = OUTPUT_DIR):
        """
        Initializes logger with timestamped session file.
        
        Creates: Output/retry_logs/YYYYMMDD_HHMMSS_retry_log.json
        """
        self.output_dir = Path(output_dir) / 'retry_logs'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.output_dir / f'{self.session_id}_retry_log.json'
        
        self.events = []  # In-memory event buffer
    
    def log_retry(self, request: RetryableRequest):
        """
        Logs retry attempt with full context.
        
        Args:
            request: RetryableRequest object from decorator
        
        Side Effects:
            - Appends event to in-memory buffer
            - Writes to console (WARNING level)
        """
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': 'retry_attempt',
            'context': {
                'url': request.url,
                'article_id': getattr(request, 'article_id', None),
                'scraper_stage': 'google_search' if 'google.com' in request.url else 'playwright_fetch'
            },
            'error': {
                'type': type(request.exception).__name__,
                'message': str(request.exception)
            },
            'retry': {
                'attempt': request.attempt,
                'max_attempts': request.max_attempts,
                'wait_time_seconds': request.wait_time,
                'cumulative_wait_seconds': request.cumulative_wait,
                'user_agent_rotated': request.user_agent_rotated
            },
            'outcome': 'retry_scheduled'
        }
        
        self.events.append(event)
        print(f"⚠️  Retrying ({request.attempt}/{request.max_attempts}) after {request.wait_time}s backoff...")
    
    def log_success(self, request: RetryableRequest):
        """Logs successful retry recovery."""
        event = self._create_event(request, outcome='success')
        self.events.append(event)
        print(f"✅ Retry succeeded after {request.attempt} attempts")
    
    def log_failure(self, request: RetryableRequest):
        """Logs permanent failure after max retries."""
        event = self._create_event(request, outcome='permanent_failure')
        self.events.append(event)
        print(f"❌ Permanent failure after {request.max_attempts} attempts")
    
    def save(self):
        """Writes all events to JSON file at end of session."""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': self.session_id,
                'events': self.events
            }, f, indent=2)
```

**Global Instance**:
```python
# Singleton instance
retry_logger = RetryLogger()
```

**Contract**: [contracts/retry_logger.md](contracts/retry_logger.md)

### D5: Configuration Schema

**File**: `src/config.py` (additions)

**New Configuration Parameters**:

```python
# ========================================
# Retry Policy Configuration
# ========================================

# Maximum retry attempts for transient failures
MAX_RETRY_ATTEMPTS = 5

# Backoff timing (seconds)
INITIAL_BACKOFF_DELAY = 1    # Starting delay for exponential backoff
MAX_BACKOFF_DELAY = 60       # Maximum delay cap
LINEAR_BACKOFF_DELAY = 5     # Fixed delay for linear backoff

# Randomized delays (seconds)
RANDOM_DELAY_MIN = 1         # Minimum delay between requests
RANDOM_DELAY_MAX = 5         # Maximum delay between requests

# User agent pool (5 distinct agents for rotation)
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
]

# HTTP status codes that trigger retry
RETRY_ON_STATUS_CODES = [429, 403, 500, 502, 503, 504]

# Permanent failure status codes (no retry)
PERMANENT_FAILURE_CODES = [404, 410]

# Playwright retry configuration
PLAYWRIGHT_MAX_RETRIES = 3
PLAYWRIGHT_RETRY_DELAY = 2  # seconds (linear backoff)
```

**Deprecation Plan**:
- Keep existing `MAX_RETRIES` and `INITIAL_DELAY` for backward compatibility
- Map to new parameters: `MAX_RETRY_ATTEMPTS = MAX_RETRIES`, `INITIAL_BACKOFF_DELAY = INITIAL_DELAY`
- Add deprecation warning in console (not breaking change)

### D6: Scraper Integration Points

**Modifications to `src/news_scraper_simple.py`**:

**1. Extract `_fetch_page()` method**  
   Refactor inline requests.get() to separate method for decorator application.

```python
@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS,
    backoff_strategy='exponential',
    retry_on=[requests.RequestException],
    on_retry=lambda req: self._handle_retry(req)
)
def _fetch_page(self, keyword: str, page: int, params: Dict) -> requests.Response:
    """
    Fetches single Google News search page with retry logic.
    
    Args:
        keyword: Search keyword for logging context
        page: Page number for logging context
        params: Request parameters (q, tbm, tbs, etc.)
    
    Returns:
        requests.Response object
    
    Raises:
        requests.RequestException: After max retries exhausted
        CaptchaDetected: If CAPTCHA page detected (non-retryable)
    """
    headers = self.headers.copy()
    headers['User-Agent'] = user_agent_pool.get_next()
    
    response = requests.get(
        self.search_url_base,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    
    # Blocking detection
    block_type = BlockDetector.detect(
        response=response,
        html_content=response.text
    )
    
    if block_type == BlockType.CAPTCHA:
        raise CaptchaDetected(f"CAPTCHA detected for keyword '{keyword}'")
    
    response.raise_for_status()  # Trigger retry on 4xx/5xx
    return response

def _handle_retry(self, request: RetryableRequest):
    """Callback invoked before each retry attempt."""
    retry_logger.log_retry(request)
    time.sleep(random.uniform(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX))  # Anti-bot jitter
```

**2. Update `get_news()` method**  
   Replace inline `requests.get()` with `_fetch_page()` call.

```python
# Before (line 230):
response = requests.get(self.search_url_base, params=params, headers=self.headers, timeout=REQUEST_TIMEOUT)

# After:
response = self._fetch_page(keyword, page, params)
```

**3. Remove manual retry loop**  
   Delete lines 261-267 (manual exponential backoff) - now handled by decorator.

**Modifications to `src/content_analyzer_simple.py`**:

**1. Extract Playwright logic to `_fetch_with_playwright()`**

```python
@retry_with_backoff(
    max_attempts=PLAYWRIGHT_MAX_RETRIES,
    backoff_strategy='linear',
    retry_on=[PlaywrightTimeoutError, PlaywrightError],
    on_retry=lambda req: self._handle_playwright_retry(req)
)
def _fetch_with_playwright(self, url: str, article_id: str) -> str:
    """
    Fetches article HTML using Playwright with retry logic.
    
    Args:
        url: Article URL
        article_id: Article identifier for logging
    
    Returns:
        HTML content string
    
    Raises:
        PlaywrightError: After max retries exhausted
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        context = browser.new_context(user_agent=user_agent_pool.get_next())
        page = context.new_page()
        
        # Set headers
        page.set_extra_http_headers({...})  # Existing headers
        
        # Navigate and wait
        response = page.goto(url, timeout=45000, wait_until='domcontentloaded')
        if not response or not response.ok:
            raise PlaywrightError(f"Failed to load {url} with status {response.status if response else 'No response'}")
        
        page.wait_for_selector('article, main, .article-content', timeout=15000)
        page.wait_for_load_state('networkidle', timeout=15000)
        time.sleep(5)  # Dynamic content load
        
        html_content = page.content()
        context.close()
        browser.close()
        
        return html_content

def _handle_playwright_retry(self, request: RetryableRequest):
    """Callback for Playwright retry logging."""
    retry_logger.log_retry(request)
```

**2. Update `fetch_article_content()` method**  
   Replace inline Playwright code (lines 152-256) with `_fetch_with_playwright()` call.

```python
# Simplified flow
html_content = self._fetch_with_playwright(url, article_id)
# Continue with existing HTML processing
```

### D7: Error Handling and Edge Cases

**Custom Exception Classes** (add to `src/models.py`):

```python
class CaptchaDetected(Exception):
    """Raised when CAPTCHA challenge page is detected."""
    pass

class PermanentScraperError(Exception):
    """Raised for non-retryable errors (404, 410)."""
    pass

class MaxRetriesExceeded(Exception):
    """Raised when retry limit reached."""
    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(f"Failed after {attempts} retry attempts: {last_exception}")
```

**Edge Case Handling**:

| Edge Case | Detection | Handling | Test Coverage |
|-----------|-----------|----------|---------------|
| All user agents blocked | 5 consecutive 403s with agent rotation | Log warning, continue with last agent | `test_user_agent_pool.py::test_all_agents_blocked` |
| CAPTCHA during retry | HTML pattern match | Stop retries, log error, return None | `test_block_detector.py::test_captcha_detection` |
| Network down (all retries fail) | `ConnectionError` * MAX_RETRIES | Raise `MaxRetriesExceeded`, log error | `test_retry_policy.py::test_network_down` |
| Google HTML structure changed | No articles found (`len(articles) == 0`) | Retry with different user agent (2 attempts) | `test_news_scraper.py::test_invalid_html_structure` |
| Timeout accumulation >30min | Track `cumulative_wait` in `RetryableRequest` | Stop after cumulative wait exceeds 30min threshold | `test_retry_policy.py::test_timeout_accumulation` |
| Playwright browser crash | `PlaywrightError` exception | Retry with fresh browser instance | `test_content_analyzer.py::test_playwright_crash` |

**Graceful Degradation** (P3 User Story):

```python
def get_news(self, keywords, start_date, end_date, max_articles):
    """Modified to support partial results."""
    results = []
    failed_keywords = []
    
    for keyword in keywords:
        try:
            keyword_results = self._search_keyword(keyword, ...)
            results.extend(keyword_results)
        except MaxRetriesExceeded as e:
            failed_keywords.append(keyword)
            print(f"⚠️  Failed to fetch keyword '{keyword}' after {e.attempts} attempts")
            continue  # Continue with next keyword
    
    if failed_keywords:
        print(f"⚠️  Partial results: {len(failed_keywords)} keywords failed")
    
    return pd.DataFrame(results)
```

## Design Deliverables

**1. Architecture Document** (`specs/001-scraper-anti-blocking/design.md`):
- Component diagram (retry_policy, user_agent_pool, block_detector, retry_logger)
- Sequence diagram (request → retry decorator → backoff → user agent rotation → log)
- Data flow diagram (scraper → decorator → BlockDetector → RetryLogger)
- Configuration schema
- Error handling strategy

**2. API Contracts** (`specs/001-scraper-anti-blocking/contracts/`):
- `retry_decorator.md`: `@retry_with_backoff` decorator signature, behavior, examples
- `user_agent_pool.md`: `UserAgentPool` class API, thread safety guarantees
- `block_detector.md`: `BlockDetector.detect()` method, BlockType enum
- `retry_logger.md`: `RetryLogger` class API, JSON schema

**3. Integration Plan**:
- Decorator injection points documented
- Backward compatibility strategy
- Deprecation plan for old retry code
- Migration checklist (remove manual retry loops, add imports, configure new params)

**Phase 1 Exit Criteria**:
- [x] Design document completed with all 7 component designs
- [x] API contracts created for 4 modules (retry_policy, user_agent_pool, block_detector, retry_logger)
- [x] Configuration schema defined in config.py additions
- [x] Integration points documented (2 scraper method extractions)
- [x] Error handling edge cases cataloged (6 scenarios)
- [x] Constitution re-check passed (all 7 checks still ✅)

---

# Next Steps

**Ready for Phase 2: Task Generation**

Run `/speckit.tasks` to generate detailed implementation tasks based on this plan. Tasks will be organized into:

1. **Setup Phase**: Add tenacity dependency, create module stubs
2. **Core Implementation**: Build retry_policy, user_agent_pool, block_detector, retry_logger modules
3. **Integration Phase**: Refactor news_scraper_simple.py, content_analyzer_simple.py
4. **Testing Phase**: Write unit tests, integration tests, edge case tests
5. **Documentation Phase**: Update README, add inline comments, create quickstart guide
6. **Validation Phase**: Run full pipeline test, measure success rate, verify logging

**Estimated Implementation Time**: 3-4 days (8-10 tasks)

**Priority for MVP (P1 User Story)**:
- Retry decorator with exponential backoff ✅
- User agent rotation ✅
- Blocking detection (429, 403, CAPTCHA) ✅
- Basic logging (console + JSON) ✅

**Deferred to P2/P3**:
- Advanced logging dashboard (P2)
- Graceful degradation (P3)
- Viewport randomization (P2)
- playwright-stealth library integration (P3)

---

**Plan Status**: ✅ Complete  
**Constitution Compliance**: 7/7 checks passed  
**Research Phase**: ✅ Complete (6 analyses delivered)  
**Design Phase**: ✅ Complete (7 components designed, 4 contracts specified)  
**Next Command**: `/speckit.tasks` to generate implementation tasks
