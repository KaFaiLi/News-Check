# News-Check

News-Check generates a monthly AI news digest for investment-banking readers. It discovers candidate stories from Google News, ranks them using metadata, fetches only the highest-value articles through Playwright Edge, analyzes the selected set with Azure OpenAI, and renders three output artifacts:

- a detailed Word report
- an HTML email body
- an Excel workbook of scored articles

This project is designed for a manual monthly run. It is not a long-running service and it does not use CLI flags for run-time configuration.

## Pipeline

1. Discover candidate articles from Google News across three topic buckets:
   - AI
   - AI in banking and finance
   - AI agents
2. Rank the full candidate pool using metadata only:
   - title and snippet relevance
   - source tier
   - recency
   - cross-source consensus
3. Stream extraction in score order through a shared Playwright Edge browser pool.
4. Keep walking the ranked pool until selection rules are satisfied:
   - top 10 articles
   - at least 3 AI-banking stories
   - maximum 3 articles per source
5. Generate per-article investment-banking insights in parallel with Azure OpenAI.
6. Render final artifacts into the Output directory.

The key efficiency choice is rank-then-stream-fetch: the pipeline usually fetches only the articles needed to fill the final selection instead of downloading the full candidate pool.

## Constraints

These are intentional project rules, not suggestions:

- Package management is uv only.
- Web fetching uses Playwright with the Edge channel only.
- LLM calls use LangChain plus Azure OpenAI only.
- Run-time tunables live in config.toml.
- Secrets live in .env.
- There are no CLI flags for changing run behavior.

## Requirements

- Python 3.11+
- uv
- Playwright Edge channel installed via Playwright
- Azure OpenAI deployment and credentials

## Quick Start

1. Clone the repository and move into it.

```powershell
git clone <your-repo-url>
cd News-Check
```

2. Install dependencies.

```powershell
uv sync
```

3. Install the Playwright Edge browser channel.

```powershell
uv run playwright install msedge
```

4. Copy `.env.example` to `.env` and fill in your Azure OpenAI values.

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-nano
AZURE_OPENAI_API_VERSION=2024-02-01
```

5. Edit `config.toml` for the month you want to cover and any query, scoring, or output changes.

6. Run the pipeline.

```powershell
uv run python -m src
```

Equivalent entry point:

```powershell
uv run main.py
```

## Configuration

### `.env`

Azure OpenAI secrets are loaded from `.env`:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

The loader prefers the repo-local `.env` file over inherited shell variables, so the workspace configuration wins even if your terminal already has Azure variables set.

### `config.toml`

All run-time behavior lives in `config.toml`.

| Section | Purpose |
| --- | --- |
| `[run]` | Date window and candidate count per topic |
| `[topics]` | Google News queries for AI, AI banking, and AI agents |
| `[selection]` | Final top-N size, AI-banking floor, per-source cap |
| `[scoring]` | Weights for topic relevance, consensus, source tier, recency |
| `[sources]` | Tiered publisher lists and multipliers |
| `[anti_blocking]` | Retry attempts, backoff, random delay, degradation threshold |
| `[parallelism]` | Worker counts for discovery, extraction, and analysis |
| `[output]` | Output directory, company name, markdown cap |
| `[llm]` | Temperature and per-article content truncation |

If `run.date_from` and `run.date_to` are not set, the pipeline defaults to the previous calendar month.

## Running the Digest

Run:

```powershell
uv run python -m src
```

The console prints:

- the selected date window
- target article count and AI-banking floor
- degradation warnings if extraction quality drops
- final artifact paths

Failures inside a stage are tracked as degradation rather than always aborting the run. That means a partially degraded run can still produce usable output, with details captured in retry logs.

## Output Artifacts

The pipeline writes files under `Output/`.

### Final artifacts

- `Output/detailed_news_report_YYYYMMDD_HHMMSS.docx`
- `Output/email_content_YYYYMMDD_HHMMSS.html`
- `Output/news_articles_YYYYMMDD_HHMMSS.xlsx`

### Supporting artifacts

- `Output/article_content/<urlhash>.md` cached article markdown
- `Output/retry_logs/<session_id>_retry_log.json` retry and degradation audit trail

The email renderer includes the top 3 selected stories. The Word report renders the full selected set.

## Repository Layout

```text
.
|-- main.py
|-- config.toml
|-- pyproject.toml
|-- src/
|   |-- __main__.py
|   |-- config.py
|   |-- document_generator.py
|   |-- models.py
|   |-- analysis/
|   |   |-- insights.py
|   |   |-- llm.py
|   |   `-- parallel_insights.py
|   |-- anti_blocking/
|   |   |-- block_detector.py
|   |   |-- retry_policy.py
|   |   |-- session_logger.py
|   |   `-- user_agents.py
|   |-- discovery/
|   |   |-- google_news.py
|   |   `-- publishers.py
|   |-- extraction/
|   |   |-- browser.py
|   |   |-- browser_pool.py
|   |   |-- fetcher.py
|   |   |-- markdown.py
|   |   `-- parallel_fetcher.py
|   |-- pipeline/
|   |   `-- graph.py
|   `-- ranking/
|       `-- scorer.py
`-- tests/
```

## Development

Install dev dependencies with the normal sync:

```powershell
uv sync
```

Run tests:

```powershell
uv run pytest --no-cov
```

Run a focused test file:

```powershell
uv run pytest tests/test_parallel_fetcher.py -v
```

Run a focused test selection:

```powershell
uv run pytest -k "banking_floor"
```

Run linting:

```powershell
uv run ruff check src tests
```

Coverage is enabled by default through `pytest.ini`; pass `--no-cov` for faster local iteration.

## Notes For Changes

- To change topics or search coverage, edit `config.toml`.
- To change ranking behavior, edit `src/ranking/scorer.py` and the scoring weights in `config.toml`.
- To change selection rules such as the AI-banking floor or per-source cap, edit `src/extraction/parallel_fetcher.py` and its tests.
- To change prompts or analysis wording, edit `src/analysis/insights.py`.
- To change output layout or copy, edit `src/document_generator.py` and the related renderer tests.

## Troubleshooting

### Missing Azure settings

If startup fails with a configuration error, verify that `.env` exists and contains all four `AZURE_OPENAI_*` variables.

### Playwright or browser startup failures

Reinstall the Edge browser channel:

```powershell
uv run playwright install msedge
```

### Degraded runs

If extraction is throttled or blocked, inspect the retry log under `Output/retry_logs/` to see the failure classifications and backoff behavior.
