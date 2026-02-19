# Feature Specification: Enhanced Scraper Resilience and Anti-Blocking

**Feature Branch**: `001-scraper-anti-blocking`  
**Created**: 2026-01-05  
**Status**: Draft  
**Input**: User description: "I would need the code to be more robust on fetching the news and prevent being blocked"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Daily News Collection (Priority: P1)

As a business auditor running the daily news aggregation script, I need the system to successfully fetch news articles even when Google News implements rate limiting or bot detection, so that I can consistently deliver timely updates to investment bank stakeholders without manual intervention.

**Why this priority**: Core functionality - without reliable scraping, the entire pipeline fails and no email reports can be generated. This directly impacts the primary use case of automated news delivery.

**Independent Test**: Run the scraper 5 times consecutively within 1 hour. System should successfully fetch articles in at least 4 out of 5 attempts, with automatic retry mechanisms handling temporary blocks.

**Acceptance Scenarios**:

1. **Given** the scraper encounters a 429 rate limit error, **When** the retry mechanism activates, **Then** the system waits with exponential backoff and successfully fetches articles on retry
2. **Given** Google News detects bot-like behavior, **When** the scraper rotates user agents and adds random delays, **Then** the system completes the scraping session without being permanently blocked
3. **Given** a network timeout occurs during fetching, **When** the retry logic engages, **Then** the system attempts up to 5 retries before gracefully failing and logging the error

---

### User Story 2 - Transparent Blocking Detection and Recovery (Priority: P2)

As a system administrator, I need clear visibility into when and why scraping failures occur, so that I can adjust retry parameters, identify patterns, and maintain system reliability without guessing at root causes.

**Why this priority**: Enables proactive maintenance and tuning. While not blocking core functionality, this significantly reduces troubleshooting time and improves long-term reliability.

**Independent Test**: Trigger a blocking scenario (e.g., rapid consecutive requests). Verify that detailed logs capture: timestamp, error type, retry count, user agent used, and recovery outcome.

**Acceptance Scenarios**:

1. **Given** the scraper is blocked by Google, **When** the error is detected, **Then** the system logs the block type (rate limit, CAPTCHA, connection refused) with timestamp and context
2. **Given** multiple retry attempts fail, **When** the maximum retry count is reached, **Then** the system generates a comprehensive error report with all attempted strategies
3. **Given** scraping completes successfully after retries, **When** reviewing logs, **Then** administrators can see the full retry timeline and which strategy succeeded

---

### User Story 3 - Gradual Degradation Under Sustained Blocking (Priority: P3)

As a news analyst, I need the system to continue functioning in a limited capacity when facing sustained blocking, so that I receive at least partial results rather than complete failure even during challenging scraping conditions.

**Why this priority**: Improves user experience during edge cases but isn't critical for MVP. The system should prioritize full success (P1) before implementing graceful degradation.

**Independent Test**: Simulate aggressive blocking (reject 70% of requests). Verify system collects at least 30% of target articles and generates a partial report with a warning note.

**Acceptance Scenarios**:

1. **Given** only 3 out of 10 keyword searches succeed, **When** article analysis begins, **Then** the system processes available articles and flags the report as "partial results"
2. **Given** persistent blocking prevents full article content fetching, **When** generating documents, **Then** the system uses available preview snippets and marks affected articles clearly
3. **Given** blocking prevents meeting the minimum 3 Fintech articles requirement, **When** ranking articles, **Then** the system relaxes the minimum threshold and logs a warning to administrators

---

### Edge Cases

- What happens when all user agents in the rotation pool are blocked simultaneously?
- How does the system handle CAPTCHA challenges that require human intervention?
- What occurs when network connectivity is completely lost during a scraping session?
- How does the system behave when Google News changes its HTML structure during a scraping run?
- What happens if retry delays accumulate to exceed reasonable execution time (e.g., >30 minutes)?

## Requirements *(mandatory)*

### Functional Requirements

**Constitution Alignment**: 
- ✅ Modular architecture - scraper stage remains independent
- ✅ Category enforcement - maintained even with partial results (P3)
- ✅ LLM-optional operation - scraping resilience doesn't depend on LLM
- ✅ Transparent scoring - blocking/retry mechanisms logged and auditable

- **FR-001**: System MUST implement exponential backoff retry logic with configurable maximum attempts (default: 5) and initial delay (default: 1 second, max: 60 seconds)
- **FR-002**: System MUST rotate through multiple user agent strings to mimic different browser types (minimum 5 distinct agents covering Chrome, Firefox, Safari, Edge)
- **FR-003**: System MUST add randomized delays (range: 1-5 seconds) between keyword searches AND between individual article content fetches to avoid bot-like timing patterns
- **FR-004**: System MUST detect common blocking responses including HTTP 429 (rate limit), 403 (forbidden), CAPTCHA pages, and connection timeouts
- **FR-005**: System MUST log all retry attempts with timestamps, error codes, strategies applied, and outcomes to enable auditing and troubleshooting
- **FR-006**: System MUST gracefully degrade when partial results are available, processing successfully fetched articles rather than failing completely
- **FR-007**: System MUST preserve existing scraper functionality when no blocking is encountered (zero-impact on successful scraping scenarios)
- **FR-008**: System MUST allow configuration of retry parameters (max attempts, delays, user agents) via centralized config file without code changes
- **FR-009**: System MUST respect HTTP status codes and avoid retrying on permanent failures (e.g., 404 Not Found, 410 Gone)
- **FR-010**: System MUST implement request headers that mimic legitimate browser behavior (Accept, Accept-Language, Accept-Encoding, Referer)

### Key Entities

- **Retry Policy**: Defines maximum attempts, backoff strategy (exponential vs linear), delay ranges, and failure thresholds for scraping operations
- **User Agent Pool**: Collection of browser user agent strings with rotation strategy to distribute requests across different apparent browser types
- **Block Detection Pattern**: Rules for identifying blocking responses including status codes, response content patterns (CAPTCHA HTML), and timeout thresholds
- **Scraping Session Metadata**: Tracks request timing, retry counts, user agents used, and success/failure rates for auditing and optimization

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System successfully completes daily news fetching in 95% of automated runs over a 30-day period (measured by successful report generation)
- **SC-002**: When encountering rate limiting, system recovers and completes scraping within 3 retry attempts in 80% of cases
- **SC-003**: Average scraping time for 100 articles remains under 5 minutes when no blocking occurs (zero performance degradation)
- **SC-004**: When 50% of requests are blocked, system still collects at least 40% of target articles (graceful degradation threshold)
- **SC-005**: Administrators can locate the block type, retry count, user agent used, and timestamp of any failed request within 2 minutes by searching the JSON log file (log clarity and completeness metric)
- **SC-006**: Zero permanent blocks lasting >24 hours occur during normal operation (sustainable scraping practices)
- **SC-007**: System maintains existing scraping accuracy - 100% of successful fetches yield valid article data with no parsing errors introduced by retry mechanisms

## Assumptions *(optional)*

1. Google News HTML structure remains stable during retry attempts within a single session
2. Network connectivity issues are transient and typically resolve within 60 seconds
3. IP address blocking is not implemented by Google News (residential IP assumed)
4. The system runs in an environment where waiting 2-5 minutes for retries is acceptable
5. CAPTCHA challenges are rare edge cases that can be handled through manual intervention alerts rather than automated solving
6. User agent rotation alone provides sufficient diversity to avoid browser fingerprinting detection
7. The existing Playwright-based content fetching already has some stealth capabilities that complement these anti-blocking measures
8. If all 5 user agents in the rotation pool are blocked simultaneously, the system will trigger a manual intervention alert, log a CRITICAL error with CAPTCHA_REQUIRED or ALL_AGENTS_BLOCKED event type, and attempt graceful degradation with partial results before failing

## Out of Scope

- Implementation of CAPTCHA solving services or human verification workflows
- Proxy server rotation or VPN integration for IP address distribution
- Browser fingerprinting evasion techniques (canvas fingerprinting, WebGL spoofing)
- Distributed scraping across multiple machines or cloud instances
- Real-time monitoring dashboard for scraping health metrics
- Machine learning-based blocking prediction or adaptive retry strategies
- Integration with third-party anti-bot services (e.g., ScraperAPI, Bright Data)
- Headless browser mode alternatives (Selenium, Puppeteer) - continues using Playwright

## Dependencies

- Existing `GoogleNewsScraper` class in `src/news_scraper_simple.py`
- Existing `ContentAnalyzerSimple.fetch_article_content()` using Playwright
- Configuration system in `src/config.py` for new retry parameters
- Logging infrastructure (standard Python `logging` module)

## Risks

- **High**: Google News may implement more aggressive bot detection that defeats simple user agent rotation and delays
- **Medium**: Increased retry delays could extend total execution time beyond acceptable limits for daily automation
- **Medium**: Exponential backoff might not be optimal for all blocking scenarios (some may require immediate retry, others longer waits)
- **Low**: User agent rotation might introduce inconsistencies in HTML parsing if different browsers receive different page structures
- **Low**: Excessive logging of retry attempts could consume significant disk space over time
