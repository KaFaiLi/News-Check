# Tasks: Enhanced Scraper Resilience and Anti-Blocking

**Input**: Design documents from `/specs/001-scraper-anti-blocking/`
**Prerequisites**: plan.md, spec.md, research.md (if created)

**Tests**: This feature includes comprehensive test tasks to ensure reliability of retry mechanisms.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency installation

- [X] T001 Create feature branch `001-scraper-anti-blocking` from main
- [X] T002 Install tenacity library: `pip install tenacity` and update requirements.txt
- [X] T003 [P] Create output directory structure: `Output/retry_logs/` and `Output/article_content/errors/`
- [X] T004 [P] Review current retry logic in src/news_scraper_simple.py (lines 234-261) and src/content_analyzer_simple.py (line 152)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core retry infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**News-Check Foundation Checklist**:
- Configuration centralized in `src/config.py` with all retry parameters defined
- Retry modules independently testable without running full scraper
- LLM usage remains properly gated by `USE_LLM` flag (no new LLM dependencies)
- Category system and scoring algorithm unchanged
- Output directory structure and file naming conventions maintained

### Foundational Configuration

- [X] T005 Add retry configuration constants to src/config.py:
  - `MAX_RETRY_ATTEMPTS = 5`
  - `INITIAL_BACKOFF_DELAY = 1` (seconds)
  - `MAX_BACKOFF_DELAY = 60` (seconds)
  - `REQUEST_TIMEOUT = 30` (seconds)
  - `RANDOM_DELAY_RANGE = (1, 5)` (seconds)
  - `RETRY_ON_STATUS_CODES = [429, 403, 500, 502, 503, 504]`

- [X] T006 Add user agent pool to src/config.py:
  ```python
  USER_AGENT_POOL = [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
  ]
  ```

### Foundational Models

- [X] T007 Add retry metadata models to src/models.py:
  - `RetryMetadata` (attempt, max_attempts, wait_time, strategy, outcome)
  - `BlockType` enum (RATE_LIMIT, FORBIDDEN, CAPTCHA, TIMEOUT, etc.)
  - `RetryEvent` (timestamp, event_type, context, error, retry, outcome)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Reliable Daily News Collection (Priority: P1) 🎯 MVP

**Goal**: Implement exponential backoff retry, user agent rotation, and random delays to achieve 95% success rate in daily scraping runs.

**Independent Test**: Run scraper 5 times consecutively within 1 hour. System should successfully fetch articles in at least 4 out of 5 attempts with automatic retry mechanisms handling temporary blocks.

### Tests for User Story 1 (Write Tests FIRST) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T008 [P] [US1] Create tests/test_user_agent_pool.py:
  - Test round-robin rotation returns different agents sequentially
  - Test random start index initialization
  - Test thread safety with concurrent calls
  - Test pool exhaustion handling (cycles back to start)
  - Test empty pool raises ValueError

- [ ] T009 [P] [US1] Create tests/test_retry_policy.py:
  - Test exponential backoff delays: 1s, 2s, 4s, 8s, 16s (capped at 60s)
  - Test max retry attempts enforcement (5 attempts then raise)
  - Test successful retry after 2nd attempt
  - Test retry_on exception filtering (retries RequestException, not ValueError)
  - Test exclude_on exception bypass (CAPTCHA skips retry)
  - Test on_retry callback invocation with correct RetryableRequest context

- [ ] T010 [P] [US1] Create tests/test_block_detector.py:
  - Test rate limit detection (HTTP 429)
  - Test forbidden detection (HTTP 403)
  - Test CAPTCHA detection (HTML content match: "captcha", "recaptcha")
  - Test timeout detection (PlaywrightTimeoutError, requests.Timeout)
  - Test connection error detection (requests.ConnectionError)
  - Test server error detection (5xx status codes)
  - Test non-retryable detection (404, 410, 401)
  - Test detect_block_type() returns correct BlockType enum

- [ ] T011 [US1] Add integration tests to tests/test_news_scraper.py:
  - Test scraper retries on 429 rate limit with exponential backoff
  - Test scraper rotates user agents on 403 forbidden
  - Test scraper adds random delays between requests (mock time.sleep)
  - Test scraper completes successfully after 2 retries
  - Test scraper fails gracefully after 5 retries
  - Test scraper preserves existing functionality when no errors occur (zero performance impact)

- [ ] T012 [US1] Add integration tests to tests/test_content_analyzer.py:
  - Test Playwright content fetch retries on timeout
  - Test Playwright user agent rotation per article
  - Test Playwright completes after retry with different user agent
  - Test Playwright saves error with retry metadata to Output/article_content/errors/

### Implementation for User Story 1

- [X] T013 [P] [US1] Create src/user_agent_pool.py:
  - Implement `UserAgentPool` class with thread-safe rotation
  - `__init__(agents: List[str])` initializes with random start index
  - `get_next() -> str` returns next user agent in round-robin sequence
  - `get_current() -> str` returns current user agent without rotation
  - `reset()` resets to random start index
  - Use `threading.Lock` for thread safety
  - Import `USER_AGENT_POOL` from config and create singleton instance

- [X] T014 [P] [US1] Create src/block_detector.py:
  - Implement `BlockType` enum (RATE_LIMIT, FORBIDDEN, CAPTCHA, TIMEOUT, CONNECTION_ERROR, SERVER_ERROR, INVALID_HTML, NON_RETRYABLE)
  - Implement `BlockDetector` class with static methods
  - `detect_block_type(response, exception, html_content) -> Optional[BlockType]` analyzes response/exception to classify block type
  - `is_retryable(block_type: BlockType) -> bool` returns False for CAPTCHA and NON_RETRYABLE
  - `get_retry_strategy(block_type: BlockType) -> str` returns "exponential" or "linear" based on block type
  - Pattern matching: HTTP status codes, exception types, HTML content regex

- [X] T015 [US1] Create src/retry_policy.py (depends on T013, T014, T007):
  - Import tenacity library decorators
  - Implement `retry_with_backoff()` decorator factory
  - Parameters: max_attempts, backoff_strategy, retry_on, exclude_on, on_retry
  - Use `tenacity.retry()` with `stop_after_attempt()` and `wait_exponential()`
  - Integrate `BlockDetector.is_retryable()` for conditional retry
  - Rotate user agent via `user_agent_pool.get_next()` on 403/429 blocks
  - Add random delay via `time.sleep(random.uniform(*RANDOM_DELAY_RANGE))`
  - Invoke on_retry callback with `RetryableRequest` context
  - Return original function result on success, raise original exception after max attempts

- [X] T016 [US1] Modify src/news_scraper_simple.py to apply retry decorator:
  - Import `retry_with_backoff` from src.retry_policy
  - Import `user_agent_pool` from src.user_agent_pool
  - Remove existing simple retry logic (lines 234-261)
  - Apply `@retry_with_backoff()` decorator to `_fetch_page()` method (create if not exists)
  - Update headers to use `user_agent_pool.get_next()` instead of static USER_AGENT
  - Ensure `response.raise_for_status()` triggers retry on 4xx/5xx
  - Add random delay between keyword searches: `time.sleep(random.uniform(*RANDOM_DELAY_RANGE))`
  - Preserve existing scraper API and return values

- [X] T017 [US1] Modify src/content_analyzer_simple.py to apply retry decorator:
  - Import `retry_with_backoff` from src.retry_policy
  - Import `user_agent_pool` from src.user_agent_pool
  - Remove hardcoded retry logic (line 152: `max_retries = 3`)
  - Apply `@retry_with_backoff()` decorator to Playwright content fetch logic
  - Update Playwright context user agent: `context.new_context(user_agent=user_agent_pool.get_next())`
  - Add retry_on for PlaywrightTimeoutError and PlaywrightError
  - Preserve existing paywall detection and error logging

- [X] T018 [US1] Add validation and error handling:
  - Validate USER_AGENT_POOL is not empty in src/user_agent_pool.py
  - Validate retry configuration values are positive integers in src/config.py
  - Ensure BlockDetector handles None response/exception gracefully
  - Add docstrings to all new functions and classes

- [X] T018a [US1] Implement legitimate browser headers (FR-010):
  - Add headers dictionary to src/retry_policy.py: Accept, Accept-Language, Accept-Encoding, Referer
  - Update src/news_scraper_simple.py to include headers in all requests: `headers={**headers, 'User-Agent': user_agent_pool.get_next()}`
  - Update src/content_analyzer_simple.py Playwright context with extra_http_headers
  - Headers must mimic Chrome/Firefox: `'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'`
  - Add `'Accept-Language': 'en-US,en;q=0.9'`, `'Accept-Encoding': 'gzip, deflate, br'`, `'Referer': 'https://www.google.com/'`

- [X] T019 [US1] Add console logging for retry operations:
  - Add INFO level logs in retry_policy.py: "Retrying (2/5) after 4s backoff..."
  - Add WARNING level logs for retry attempts with block type
  - Add ERROR level logs for permanent failure after max retries
  - Add DEBUG level logs for user agent rotation events
  - Use standard Python `logging` module (no new dependencies)

**Checkpoint**: At this point, User Story 1 should be fully functional - run test suite and validate 4/5 success rate in consecutive runs

---

## Phase 4: User Story 2 - Transparent Blocking Detection and Recovery (Priority: P2)

**Goal**: Implement comprehensive logging of retry events with timestamps, error types, retry counts, strategies, and outcomes to enable proactive troubleshooting.

**Independent Test**: Trigger a blocking scenario (e.g., rapid consecutive requests). Verify that detailed logs capture: timestamp, error type, retry count, user agent used, and recovery outcome.

### Tests for User Story 2 (Write Tests FIRST) ⚠️

- [X] T020 [P] [US2] Create tests/test_retry_logger.py:
  - Test log_retry_event() creates JSON file in Output/retry_logs/
  - Test log format matches schema (session_id, events array, timestamp ISO 8601)
  - Test retry metadata includes: attempt, max_attempts, wait_time, cumulative_wait, user_agent_rotated
  - Test multiple events appended to same session log file
  - Test error context includes URL, keyword, article_id, scraper_stage
  - Test outcome field correctly set: "retry_scheduled", "success", "permanent_failure"
  - Test session_id uses YYYYMMDD_HHMMSS format

- [ ] T021 [US2] Add integration tests to tests/test_news_scraper.py:
  - Test retry logs generated after scraping session with blocks
  - Test log file contains all retry events in chronological order
  - Test cumulative wait time correctly calculated across retries
  - Test user agent rotation logged for 403/429 blocks

- [ ] T022 [US2] Add integration tests to tests/test_content_analyzer.py:
  - Test enhanced error logs in Output/article_content/errors/ include retry metadata
  - Test error JSON contains: article_id, error_type, retry_count, user_agents_tried, timestamps

### Implementation for User Story 2

- [X] T023 [P] [US2] Create src/retry_logger.py:
  - Implement `RetryLogger` class with session-based logging
  - `__init__()` generates session_id with timestamp (YYYYMMDD_HHMMSS)
  - `log_retry_event(event: RetryEvent)` appends event to session log file
  - Log file path: `Output/retry_logs/{session_id}_retry_log.json`
  - JSON schema: `{"session_id": str, "events": [RetryEvent]}`
  - `get_session_summary() -> dict` returns statistics (total_retries, success_rate, avg_wait_time)
  - Create singleton instance for import in other modules

- [X] T024 [US2] Integrate RetryLogger into src/retry_policy.py:
  - Import `retry_logger` singleton from src.retry_logger
  - In retry_with_backoff decorator, create RetryEvent on each attempt
  - Call `retry_logger.log_retry_event()` before each retry
  - Populate RetryEvent with: timestamp, context (URL, keyword), error details, retry metadata, outcome
  - Log final outcome after max retries or success

- [ ] T025 [US2] Enhance error logging in src/news_scraper_simple.py:
  - On permanent failure, save error to Output/article_content/errors/error_{keyword}_{timestamp}.json
  - Include retry metadata: total_attempts, user_agents_tried, cumulative_wait_time, block_types_encountered
  - Include context: keyword, URL, timestamp, final_error_message

- [X] T026 [US2] Enhance error logging in src/content_analyzer_simple.py:
  - Modify existing error JSON (Output/article_content/errors/error_{article_id}.json)
  - Add retry_metadata field with: attempts, wait_times, user_agents, strategies_applied
  - Preserve existing error fields (article_id, error_type, timestamp, preview_content)

- [X] T027 [US2] Add comprehensive console logging:
  - INFO: "Retry session started: {session_id}"
  - WARNING: "Retry attempt 2/5: Rate limit detected (429), waiting 4s..."
  - INFO: "Retry successful after 2 attempts, total wait: 5s"
  - ERROR: "Permanent failure after 5 attempts: {error_message}"
  - DEBUG: "User agent rotated: {old_agent} -> {new_agent}"
  - Use logging.getLogger(__name__) for module-level loggers

**Checkpoint**: At this point, User Story 2 should be fully functional - trigger blocking and verify detailed logs are generated with all required metadata

---

## Phase 5: User Story 3 - Gradual Degradation Under Sustained Blocking (Priority: P3)

**Goal**: Enable system to continue functioning with partial results when facing sustained blocking, generating reports with clear warnings rather than complete failure.

**Independent Test**: Simulate aggressive blocking (reject 70% of requests). Verify system collects at least 30% of target articles and generates a partial report with a warning note.

### Tests for User Story 3 (Write Tests FIRST) ⚠️

- [ ] T028 [P] [US3] Add integration tests to tests/test_news_scraper.py:
  - Test scraper continues with partial results when 70% of keywords fail
  - Test scraper returns articles from successful keywords only
  - Test scraper flags results as "partial" when not all keywords succeeded
  - Test scraper logs warning: "Partial results: 3/10 keywords succeeded"

- [ ] T029 [P] [US3] Add integration tests to tests/test_content_analyzer.py:
  - Test analyzer processes available articles when 50% of content fetches fail
  - Test analyzer marks articles with failed content as "preview_only"
  - Test analyzer relaxes 3 Fintech minimum when insufficient articles available
  - Test analyzer logs warning when category minimum not met

- [ ] T030 [US3] Add integration tests to tests/test_document_generator.py:
  - Test brief summary generated with partial results warning
  - Test detailed report includes disclaimer about missing content
  - Test HTML email contains warning banner for partial results
  - Test document metadata includes: total_articles_attempted, successful_fetches, partial_result_flag

### Implementation for User Story 3

- [ ] T031 [US3] Modify src/news_scraper_simple.py for graceful degradation:
  - Catch and log permanent failures for individual keywords without stopping entire scrape
  - Track successful vs. failed keyword searches
  - Return partial results with metadata: `{"articles": [...], "partial": True, "success_rate": 0.3, "failed_keywords": [...]}`
  - Add `allow_partial_results` parameter to `get_news()` method (default: True)
  - Log warning when partial results returned: "Partial results: {successful}/{total} keywords succeeded"

- [ ] T032 [US3] Modify src/content_analyzer_simple.py for graceful degradation:
  - Continue ranking even when some articles have no full content
  - Mark articles with fetch failures as `content_available=False`
  - In `rank_articles()`, relax 3 Fintech minimum if insufficient total articles:
    - If total articles < 10, set minimum to `max(1, total_articles * 0.3)`
    - Log warning: "Relaxed Fintech minimum to {new_minimum} due to partial results"
  - Add `partial_results` metadata to ranked articles output

- [ ] T033 [US3] Modify src/document_generator.py to handle partial results:
  - Add warning banner to brief summary: "⚠️ Partial Results: Some articles could not be retrieved"
  - Add disclaimer section to detailed report:
    - "Note: This report contains partial results due to scraping limitations"
    - List failed keywords and unavailable article counts
  - Add warning box to HTML email (yellow background, icon):
    - "⚠️ Partial Results Available - {success_rate}% of articles retrieved"
  - Include metadata in document properties: partial_result_flag, success_rate

- [ ] T034 [US3] Add partial results statistics to retry logs:
  - In src/retry_logger.py, add `get_degradation_metrics() -> dict`
  - Metrics: total_requests, successful_requests, failed_requests, success_rate, degraded_mode_triggered
  - Include in session summary JSON

- [ ] T035 [US3] Update src/models.py for partial results:
  - Add `PartialResultMetadata` model: success_rate, total_attempted, successful_fetches, failed_keywords, articles_unavailable
  - Add `content_available: bool` field to existing article models
  - Add `partial_results_mode: bool` field to report generation models

**Checkpoint**: All user stories should now be independently functional - system handles full success, retries, comprehensive logging, and graceful degradation

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [ ] T036 [P] Update documentation in README.md:
  - Add "Anti-Blocking Features" section documenting retry mechanisms
  - Document new configuration parameters in src/config.py
  - Add troubleshooting guide for common blocking scenarios
  - Document retry log format and location

- [ ] T037 [P] Add examples to docs/:
  - Create docs/retry_configuration.md with tuning guide
  - Create example retry log JSON in docs/examples/
  - Create example partial results report screenshot

- [ ] T038 Code cleanup and refactoring:
  - Remove commented-out old retry logic from src/news_scraper_simple.py
  - Ensure consistent error handling patterns across all modules
  - Add type hints to all new functions
  - Run linting: `flake8 src/ tests/`

- [ ] T039 [P] Performance optimization:
  - Profile scraping time with/without blocking to verify zero overhead claim
  - Optimize user agent pool to avoid excessive lock contention
  - Ensure retry logs don't consume excessive disk space (implement rotation if needed)

- [ ] T040 [P] Run complete test suite validation:
  - `pytest tests/ -v --cov=src --cov-report=html`
  - Verify all new tests pass
  - Verify coverage of retry_policy.py, user_agent_pool.py, block_detector.py, retry_logger.py >= 90%
  - Verify no regressions in existing tests

- [ ] T041 Integration validation:
  - Run full pipeline with main.py (keyword scraping → analysis → document generation)
  - Verify documents generated successfully with retry logs
  - Manually trigger blocking scenario (rapid requests) and verify recovery
  - Validate 95% success rate over 5 consecutive runs

- [ ] T042 [P] Update generate_example_email.py:
  - Add optional `--partial-results` flag to generate example with warnings
  - Include sample retry log reference in example output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User Story 1 (P1) can start after Phase 2 - No dependencies on other stories
  - User Story 2 (P2) can start after Phase 2 and US1 completion (depends on retry_policy.py from US1)
  - User Story 3 (P3) can start after Phase 2 and US1 completion (uses retry infrastructure from US1)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Creates core retry infrastructure
- **User Story 2 (P2)**: Depends on US1 completion (T015: retry_policy.py must exist) - Adds logging layer
- **User Story 3 (P3)**: Depends on US1 completion (uses retry mechanisms) - Can run parallel with US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Core modules (user_agent_pool, block_detector, retry_policy) before scraper modifications
- Models before services
- Scraper modifications before analyzer modifications (both use same retry decorator)
- Logging integration after core functionality works
- Story complete and validated before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T003 and T004 can run in parallel
- **Foundational (Phase 2)**: T005 and T006 (configuration) can run in parallel
- **User Story 1 Tests**: T008, T009, T010 can all be written in parallel (different test files)
- **User Story 1 Implementation**: T013 (user_agent_pool) and T014 (block_detector) can run in parallel (independent modules)
- **User Story 2 Tests**: T020, T021, T022 can run in parallel
- **User Story 2 Implementation**: T023 (retry_logger) can start immediately after US1 foundation is complete
- **User Story 3 Tests**: T028, T029, T030 can run in parallel
- **User Story 3 Implementation**: T031 (scraper degradation) and T032 (analyzer degradation) can run in parallel after US1 complete
- **Polish (Phase 6)**: T036, T037, T039, T040, T042 can run in parallel

---

## Parallel Example: User Story 1 Foundation

```bash
# Launch all tests for User Story 1 together:
Task T008: "Create tests/test_user_agent_pool.py"
Task T009: "Create tests/test_retry_policy.py"
Task T010: "Create tests/test_block_detector.py"

# Launch all core modules for User Story 1 together (after tests written):
Task T013: "Create src/user_agent_pool.py"
Task T014: "Create src/block_detector.py"

# Then sequentially (T015 depends on T013 and T014):
Task T015: "Create src/retry_policy.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only - Reliable Daily News Collection)

1. Complete Phase 1: Setup (install tenacity, create directories)
2. Complete Phase 2: Foundational (add configuration, models)
3. Complete Phase 3: User Story 1 (exponential backoff + user agent rotation + random delays)
4. **STOP and VALIDATE**: Run test suite, execute 5 consecutive scraping runs, verify 4/5 success rate
5. Deploy/demo if ready - Core anti-blocking functionality complete

### Incremental Delivery

1. **Foundation** (Setup + Foundational) → Configuration and dependencies ready
2. **+ User Story 1** → Test independently with consecutive runs → Deploy/Demo (MVP! Core retry working)
3. **+ User Story 2** → Test independently with blocking scenarios → Deploy/Demo (Full observability)
4. **+ User Story 3** → Test independently with simulated high blocking → Deploy/Demo (Production-ready graceful degradation)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (critical path)
2. **Once Foundational is done:**
   - Developer A: User Story 1 (core retry infrastructure) - MUST complete first
   - Developer B: Prepare tests for User Story 2 and 3 while waiting
3. **Once User Story 1 is complete:**
   - Developer A: User Story 2 (logging layer)
   - Developer B: User Story 3 (graceful degradation)
4. **Polish phase** can be distributed across team

---

## Success Validation Checklist

After completing all phases, verify the following success criteria from spec.md:

- [ ] **SC-001**: System successfully completes daily news fetching in 95% of automated runs over 30-day period
  - Validation: Run scraper 20 times over 1 week, track success rate
  
- [ ] **SC-002**: When encountering rate limiting, system recovers within 3 retry attempts in 80% of cases
  - Validation: Mock 429 responses, verify 80% recover by attempt 3
  
- [ ] **SC-003**: Average scraping time remains under 5 minutes for 100 articles when no blocking occurs
  - Validation: Benchmark clean scraping runs, ensure no performance degradation
  
- [ ] **SC-004**: When 50% of requests blocked, system still collects at least 40% of target articles
  - Validation: Mock 50% failure rate, verify ≥40% articles returned
  
- [ ] **SC-005**: Administrators can identify blocking patterns within 2 minutes of reviewing logs
  - Validation: User acceptance test - give admin sample retry log, time pattern identification
  
- [ ] **SC-006**: Zero permanent blocks lasting >24 hours during normal operation
  - Validation: Long-term monitoring over 30 days
  
- [ ] **SC-007**: 100% of successful fetches yield valid article data with no parsing errors
  - Validation: Verify retry mechanisms don't break article parsing

---

## Notes

- **[P] tasks** = different files, no dependencies, can run in parallel
- **[Story] label** maps task to specific user story for traceability
- **Tests-first approach**: All test tasks explicitly marked to write before implementation
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Constitution compliance**: All changes preserve modular architecture, category enforcement, LLM-optional operation, and transparent scoring
- **Zero performance impact**: When no blocking occurs, system should have zero overhead from retry mechanisms

---

## Risk Mitigation

From spec.md risks section:

- **Risk**: Google News may defeat simple user agent rotation
  - **Mitigation**: US1 implements 5 diverse user agents + random delays. US3 enables partial results if detection advances
  
- **Risk**: Increased retry delays extend execution time
  - **Mitigation**: US1 caps max backoff at 60s. US3 allows partial results rather than waiting indefinitely
  
- **Risk**: Exponential backoff not optimal for all scenarios
  - **Mitigation**: BlockDetector (T014) selects strategy based on block type. Configuration in config.py allows tuning
  
- **Risk**: User agent rotation introduces HTML parsing inconsistencies
  - **Mitigation**: All user agents use Windows desktop browsers with similar rendering. US1 tests (T011) validate parsing consistency
  
- **Risk**: Excessive retry logging consumes disk space
  - **Mitigation**: T039 implements log rotation if needed. JSON format is compact

---

**Total Tasks**: 42 tasks
**Estimated MVP (US1 only)**: 19 tasks (Setup + Foundational + US1)
**Parallel Opportunities**: 15+ tasks can run in parallel across phases
**Test Coverage**: 13 dedicated test tasks + integration validation
