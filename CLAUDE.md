# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

News-Check is a **monthly AI-news digest** generator for investment-banking employees. The user runs the script manually (typically once a month). The pipeline:

1. **Discovers** candidate articles from Google News for three topics — AI / AI in Banking & Finance / AI Agents — over a configurable date window. Queries fan out across a `BrowserPool` so multiple searches scrape concurrently.
2. **Ranks** all candidates using metadata only (title, snippet, source, recency, cross-source consensus). No article body is needed for scoring.
3. **Streams extraction** in rank order through the same `BrowserPool`. Walks the sorted pool, fetches each article's full rendered HTML via Playwright Edge, converts to markdown. **On any failure the next-ranked candidate slides up — there is no buffer.** Stops once the top 10 is filled with ≥3 AI-banking articles and per-source cap respected.
4. **Analyses** the selected articles in parallel through Azure OpenAI (via LangChain) — IB-relevant per-article insights, then a single cross-article monthly synthesis paragraph.
5. **Renders** three locked-format artifacts: detailed Word `.docx` (top 10 + Monthly Themes synthesis + TOC), HTML email body (top 3 cards), raw `.xlsx` of scores.

The key efficiency choice is **rank-then-stream-fetch**: only ~10–15 articles are fetched in the typical run (the top of the ranked pool, plus next-ranked replacements for any that fail), not all ~150 candidates. The streaming logic lives in `src/extraction/parallel_fetcher.py:fetch_and_select`.

## Ground rules (non-negotiable)

- **Package management: `uv` only.** Dependencies live in `pyproject.toml`. Use `uv add <pkg>`, `uv sync`, `uv run <cmd>`. Never bring back `requirements.txt` or bare `pip`.
- **Web fetching: Playwright with `channel="msedge"` only.** No `requests`, no `httpx`, no plain Chromium. The browser is wrapped by `src/extraction/browser.py:EdgeBrowser`, which already handles stealth, UA rotation, viewport/locale/timezone spoofing — extend that, don't bypass it.
- **LLM stack: LangChain (langchain-core + langchain-openai) + Azure OpenAI only.** All model calls flow through `src/analysis/llm.py:build_chat_model` (returns `AzureChatOpenAI`). No direct `openai` SDK calls, no other providers. The pipeline orchestration is plain Python — langgraph was removed.
- **Run-time tunables live in `config.toml`.** Secrets (Azure keys/endpoint/deployment/api-version) live in `.env`. The two are loaded by `src/config.py:load_settings`. CLI flags are intentionally not used.

If a request would violate one of these, stop and confirm before proceeding.

## Architecture

```
src/
  __main__.py             entry point — `uv run python -m src`
  config.py               loads config.toml + .env into a frozen Settings dataclass
  models.py               Pydantic: Article, ScoredArticle, ArticleAnalysis, DegradationStatus, MonthlyDigest
  document_generator.py   .docx / .html / .xlsx output (LOCKED format, copy-only edits)
  discovery/
    google_news.py        Google News queries fanned across BrowserPool, parsed into candidate URLs
    publishers.py         tier-1 / tier-2 / tier-3 domain lookup
  extraction/
    browser.py            Single-thread EdgeBrowser (still useful in tests/scripts; not used by the live pipeline)
    browser_pool.py       N-worker thread pool, each owning its own Playwright + Edge browser context
    fetcher.py            URL → full rendered HTML, wrapped by retry policy (single-thread variant)
    parallel_fetcher.py   STREAMING rank-order fetch + selection (the production extractor)
    markdown.py           trafilatura → html2text fallback → cached to Output/article_content/<urlhash>.md
  ranking/
    scorer.py             weighted score (topic × consensus × tier × recency); no selection here
  analysis/
    llm.py                AzureChatOpenAI factory (one shared instance per run)
    insights.py           per-article structured-output prompt → ArticleAnalysis
    parallel_insights.py  ThreadPoolExecutor over selected articles for concurrent LLM calls
    synthesis.py          cross-article monthly themes paragraph (sequential)
  pipeline/
    graph.py              plain-Python orchestration: discover → rank → fetch_select → analyze → render
  anti_blocking/
    block_detector.py     classify 403/429/CAPTCHA/timeout/empty-body
    retry_policy.py       run_with_retry — exponential backoff, UA rotation, classification-driven
    user_agents.py        rotating UA pool
    session_logger.py     JSON session log → Output/retry_logs/<session_id>_retry_log.json

config.toml               run-time tunables (date range, queries, weights, tiers, anti-blocking)
.env (gitignored)         AZURE_OPENAI_API_KEY / ENDPOINT / DEPLOYMENT / API_VERSION
```

The whole pipeline is invoked via `src/pipeline/graph.py:run_pipeline`, which calls each phase function (`discover` → `rank` → `fetch_select` → `analyze` → `render`) in sequence and threads a shared `BrowserPool`, `SessionLogger`, and `DegradationStatus` through them. Failures inside a phase are recorded into `degradation` rather than raised, so a partial run still produces output with a warning banner.

## What is locked vs. open to change

- **Locked: output format.** `document_generator.py` produces specific layouts, fonts, the company-red `#E9041E` accent, card structure, and footer. Treat the visual contract as fixed; only copy strings have been adapted for the monthly IB context. If you need to alter visible text, update both the docx + email paths and the matching test in `tests/test_document_generator.py`.
- **Locked: the three-rule contract above.** uv / Playwright Edge / LangChain+Azure are not negotiable.
- **Open: everything else.** Scoring weights, query lists, tier members, anti-block knobs all live in `config.toml` — change them there, not in code. Module boundaries, prompt phrasing, retry tactics, and discovery sources can all be redesigned when the goal warrants it.

## Common commands

```powershell
uv sync                                # install deps
uv run playwright install msedge       # install Edge channel (one-off; --force to upgrade)
uv run main.py                         # run the full pipeline (equivalent to `uv run python -m src`)
uv run pytest --no-cov                 # run tests fast, no coverage
uv run pytest tests/test_selector.py -v
uv run pytest -k "banking_floor"       # single test by name pattern
uv run ruff check src tests            # lint
```

The pipeline has two equivalent entry points: `main.py` (root) and `src/__main__.py`. `main.py` is a thin shim that re-exports `src.__main__.main`; both go through the same `load_settings → run_pipeline` path. There are no CLI arguments — edit `config.toml` to change the run.

Test config lives in `pytest.ini` (coverage on by default — pass `--no-cov` for speed during iteration).

## Where to look when adding features

- Worker-count tuning → `[parallelism]` in `config.toml` (`discovery_workers`, `extraction_workers`, `analysis_workers`). Higher values = faster but more chance of being throttled.
- New scoring signal → `src/ranking/scorer.py` plus a weight in `[scoring]` of `config.toml` and a fixture-driven test in `tests/test_scorer.py`.
- Selection rule changes (banking floor, per-source cap) → live in `src/extraction/parallel_fetcher.py:fetch_and_select` and `_trim_to_selection`. Tests in `tests/test_parallel_fetcher.py`.
- New topic / changed queries → edit `config.toml` only; the pipeline reads them through `Settings.topics`.
- New publisher tier or boost → `config.toml` `[sources]`. Tier lookup is `src/discovery/publishers.py:classify_tier`.
- New anti-bot tactic → `src/extraction/browser.py` (stealth init script + context options) or `src/anti_blocking/retry_policy.py` (backoff/rotation behaviour).
- New prompt or prompt change → `src/analysis/insights.py` for per-article, `src/analysis/synthesis.py` for cross-article. Keep the system prompt static (prompt-cache friendly).
- New output column / artifact → extend `src/document_generator.py` and update the matching renderer call in `src/pipeline/graph.py:render`.

## Things easy to get wrong here

- Don't reintroduce `requests`/`httpx`. All fetches go through `EdgeBrowser` + `PageFetcher`.
- Don't call `AzureChatOpenAI(...)` directly — use `build_chat_model(settings.azure, settings.llm)` so config flows through one place.
- Don't bypass the retry classification — every fetch should produce an `AttemptResult` with a `BlockClassification`. Raising an exception inside the fetch closure is allowed (it gets reclassified), but silent failure isn't.
- Don't add CLI flags for run-time options. Edit `config.toml`. (CLI invocation is `uv run python -m src` with no arguments by design.)
- `Output/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` are gitignored and can be deleted at any time without affecting state.
- `README.md` is from the pre-rebuild codebase; it's outdated. This file (CLAUDE.md) is the canonical reference.
