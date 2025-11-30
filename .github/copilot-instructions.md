# News-Check AI Coding Agent Instructions

## Project Overview
News-Check is a Python news aggregation and analysis tool that scrapes Google News, analyzes articles using keyword matching and LLM insights, and generates Word/HTML reports for email distribution.

## Architecture & Data Flow
**Main Pipeline (`main.py`):**
1. `GoogleNewsScraper` → Scrapes Google News HTML (not RSS) for keywords
2. `ContentAnalyzerSimple` → Deduplicates, scores, categorizes, fetches full content
3. `DocumentGenerator` → Generates brief/detailed Word docs + HTML email content

**Key Components:**
- `src/news_scraper_simple.py`: HTML scraping via BeautifulSoup (not feedparser). Uses `tbm=nws` parameter for Google News search. Parses relative time strings ("2 hours ago").
- `src/content_analyzer_simple.py`: Playwright-based content fetching with paywall detection. Keyword-based scoring (60%) + trending score (40%). **Enforces minimum 3 Fintech articles** in top results by replacing lower-scored non-Fintech articles.
- `src/document_generator.py`: Creates Word documents using `python-docx`. Generates LLM-powered overall summaries.
- `src/config.py`: Configuration hub - OpenAI API settings, LLM toggle, output directory.

## Critical Patterns

### Category System
Articles are categorized into: **AI Development**, **Fintech**, **GenAI Usage**, **Other**
- Keywords defined in `ContentAnalyzerSimple.__init__()` dictionary
- **Hard requirement:** Top articles must contain ≥3 Fintech articles (`rank_articles()` enforces this)
- Primary category determined by highest keyword score

### Scoring Algorithm
```python
# Initial scoring: keyword_score only (0-1 range)
# Updated scoring (after trending): 
overall_score = 0.6 * keyword_score + 0.4 * trending_score
```
- Trending score considers: duplicate frequency, recency (exponential decay), source diversity
- Time parsing handles both relative ("5 hours ago") and absolute date formats

### Paywall Handling
- Known paywall domains listed in `paywall_domains` dict (`wsj.com`, `nytimes.com`, etc.)
- Playwright with stealth mode attempts content extraction
- Falls back to preview/teaser content if paywalled
- Saves errors to `Output/article_content/{article_id}_error.json` for debugging

### LLM Integration
- Uses OpenRouter API (`OPENAI_API_BASE = 'https://openrouter.ai/api/v1'`)
- Model: `openai/gpt-4o-mini-2024-07-18`
- **Must set custom headers:** `HTTP-Referer` and `X-Title` for OpenRouter
- LLM generates: article insights (3 bullet points), overall summaries

## Development Workflows

### Running the Application
```powershell
# Setup (first time)
pip install -r requirements.txt
playwright install

# Configure API key in src/config.py
OPENAI_API_KEY = 'your_key_here'

# Run main pipeline
python main.py
```

### Testing
```powershell
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_content_analyzer.py -v

# Coverage report generated in htmlcov/
```
- Uses `pytest` with `pytest-cov`, `pytest-mock`
- Test files mirror `src/` structure
- Mock LLM responses in tests (`@patch('langchain_openai.ChatOpenAI')`)

### Generating Example Email
```powershell
python generate_example_email.py
```
Creates sample HTML email output for testing without running full scraper.

## Configuration Points

### src/config.py Key Settings
- `USE_LLM`: Toggle LLM analysis (keyword-only mode if False)
- `LLM_THRESHOLD`: Min keyword score to trigger LLM (default 0.1)
- `MAX_RETRIES`: Scraper retry attempts (default 5)
- `OUTPUT_DIR`: Where reports/content are saved (default 'Output')

### Search Parameters (main.py)
- `keywords`: List of search terms (AI/Fintech focused)
- `max_articles_per_keyword`: Limit per keyword (default 100)
- `start_date`/`end_date`: Date range (default: last 7 days)
- `top_n`: Number of top articles to analyze in depth (default 10)

## Output Structure
```
Output/
├── news_articles.xlsx              # Raw scraped data
├── brief_news_summary_*.docx       # Top 3 articles summary
├── detailed_news_report_*.docx     # All top articles with analysis
├── email_content_*.html            # Email-ready HTML
└── article_content/                # Fetched article content + errors
    ├── {article_id}_content.json
    └── {article_id}_error.json
```

## Common Gotchas
- **Google HTML structure changes:** Scraper relies on CSS selectors (`.WlydOe`, `.SoaBEf`) that may break. Check `news_scraper_simple.py` selectors if no results.
- **OpenRouter headers required:** LLM calls fail without `HTTP-Referer` and `X-Title` headers.
- **Fintech enforcement:** `rank_articles()` will replace lower-scored articles to maintain ≥3 Fintech articles - not a bug.
- **Playwright timeout:** Default 30s timeout for content fetching. Adjust `navigation_timeout` if needed.
- **.env file not used:** API keys configured directly in `src/config.py` (not via dotenv).

## Dependencies of Note
- `playwright`: Browser automation for content fetching (requires `playwright install`)
- `langchain-openai`: LLM integration via OpenRouter
- `fuzzywuzzy`: Duplicate detection via title similarity
- `python-docx`: Word document generation
- `beautifulsoup4`: HTML parsing for scraping
- `html2text`: Convert HTML to markdown for content extraction

## Pydantic Models
Structured outputs defined in `src/models.py`:
- `ArticleAnalysis`: Relevance score, category, impact level, key points
- `TrendAnalysis`: Key trends, industry developments, category insights
- `BriefSummary`, `DetailedReport`: Document generation schemas
