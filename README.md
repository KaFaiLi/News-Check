# News-Check

A Python-based news aggregation and analysis tool that fetches, analyzes, and summarizes news articles from various sources with **intelligent anti-blocking mechanisms** for reliable daily operation.

## ✨ Key Features

### News Aggregation & Analysis
- **News Aggregation**: Fetches news articles from Google News with HTML scraping
- **Content Analysis**: Analyzes article content using keyword matching and LLM-based insights
- **Trending Analysis**: Identifies trending topics and calculates article relevance scores
- **Category-based Filtering**: Organizes articles into categories (AI Development, Fintech, GenAI Usage)
- **Minimum Category Requirements**: Ensures minimum representation of Fintech articles (at least 3) in top results
- **Smart Content Extraction**: Handles paywalled content using Playwright with stealth mode
- **Automated Summaries**: Generates both brief and detailed summaries of news articles
- **Email-ready Output**: Creates formatted HTML content ready for email distribution

### 🛡️ Anti-Blocking System (NEW)
- **Intelligent Block Detection**: Automatically detects and classifies blocks (rate limits, CAPTCHAs, timeouts)
- **Exponential Backoff Retry**: Smart retry with increasing delays (max 5 attempts)
- **User Agent Rotation**: Rotates through legitimate browser user agents on 403/429 responses
- **Graceful Degradation**: Collects partial results when sustained blocking occurs
- **Comprehensive Logging**: JSON-based session logs for all retry events
- **Degradation Warnings**: Visible alerts in reports when operating under degraded conditions

**See [Anti-Blocking Guide](docs/ANTI_BLOCKING_GUIDE.md) for detailed documentation.**

## Requirements

- Python 3.8+
- Required Python packages (see `requirements.txt`):
  - pandas
  - python-docx
  - beautifulsoup4
  - requests
  - fuzzywuzzy
  - python-Levenshtein
  - langchain
  - langchain-core
  - langchain-openai
  - playwright
  - html2text
  - tenacity (for retry logic)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/News-Check.git
cd News-Check
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Set up environment variables:
Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Run the main script:
```bash
python main.py
```

2. The script will:
   - Fetch recent news articles
   - Analyze and categorize them
   - Ensure minimum Fintech article representation
   - Generate summaries and reports
   - Create email-ready content

3. Output files will be created in the `Output` directory:
   - `brief_news_summary_[timestamp].docx`: Concise summary of top articles
   - `detailed_news_report_[timestamp].docx`: Detailed analysis of all articles
   - `email_content_[timestamp].html`: Formatted HTML for email distribution
   - `news_articles.xlsx`: Raw article data

## Configuration

The script can be configured by modifying the following parameters in `src/config.py`:

### Basic Configuration
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_API_BASE`: Base URL for OpenAI API (Azure OpenAI endpoint)
- `USE_LLM`: Enable/disable LLM-based analysis (default: True)
- `LLM_THRESHOLD`: Score threshold for LLM analysis (default: 0.1)
- `OUTPUT_DIR`: Directory for output files (default: 'Output')

### Anti-Blocking Configuration
- `MAX_RETRY_ATTEMPTS`: Maximum retry attempts for blocked requests (default: 5)
- `INITIAL_BACKOFF_DELAY`: Initial backoff delay in seconds (default: 1)
- `MAX_BACKOFF_DELAY`: Maximum backoff delay cap (default: 60)
- `RANDOM_DELAY_RANGE`: Random delay between requests in seconds (default: (1, 5))
- `USER_AGENT_POOL`: List of user agents for rotation

### Degradation Settings
- `ENABLE_GRACEFUL_DEGRADATION`: Enable degradation mode (default: True)
- `MIN_SUCCESS_THRESHOLD`: Minimum success rate before degrading (default: 0.6)
- `MAX_CONSECUTIVE_FAILURES`: Max failures before degraded mode (default: 3)
- `COLLECT_PARTIAL_RESULTS`: Collect partial results on failure (default: True)
- `INCLUDE_DEGRADATION_WARNING`: Add warnings to reports (default: True)

**See [Anti-Blocking Guide](docs/ANTI_BLOCKING_GUIDE.md) for detailed configuration examples.**

## Article Categories

Articles are categorized into:
- **AI Development**: Articles about AI research, neural networks, and technical developments
- **Fintech**: Articles about financial technology, digital banking, and payment systems
- **GenAI Usage**: Articles about generative AI applications and implementations
- **Other**: Articles that don't fit into the above categories

## Minimum Category Requirements

The system ensures that at least 3 Fintech articles are included in the top results. If fewer than 3 Fintech articles are found in the initial top results:
1. The system will look for additional Fintech articles in the remaining pool
2. Lower-scoring non-Fintech articles will be replaced with higher-scoring Fintech articles
3. If insufficient Fintech articles are available, a warning will be displayed

## Error Handling

The system includes robust error handling for:
- **Network issues**: Automatic retry with exponential backoff
- **Rate limiting (429)**: User agent rotation and backoff delays
- **Forbidden responses (403)**: User agent rotation
- **Server errors (5xx)**: Retry with appropriate delays
- **Paywalled content**: Playwright stealth mode extraction
- **CAPTCHA detection**: Skip non-retryable blocks
- **Invalid URLs**: Graceful error logging
- **Content extraction failures**: Fallback to preview content
- **Sustained blocking**: Graceful degradation with partial results
- **API rate limits**: Automatic backoff and retry

All errors are logged to:
- **Console**: Real-time feedback with emoji indicators
- **Retry Logs**: `Output/retry_logs/{session_id}_retry_log.json`
- **Error Files**: `Output/article_content/errors/error_{article_id}.json`

## Monitoring & Logs

### Retry Logs
Location: `Output/retry_logs/`

Each session creates a timestamped JSON log with:
- All retry events with metadata
- Block types detected
- Wait times and cumulative delays  
- User agent rotation events
- Degradation status

### Console Output
Real-time status indicators:
```
✓ HTML fetched successfully
⚠️ Block type: rate_limit. Retrying (2/5) after 2.0s...
⚠️ Entering degraded mode: 3 consecutive failures
```

### Report Warnings
Degradation warnings automatically appear in:
- Word documents (brief and detailed)
- HTML email content
- Console summary

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Directory Structure

```
News-Check/
├── main.py                          # Main entry point
├── src/
│   ├── __init__.py                 # Package initialization
│   ├── news_scraper_simple.py      # News scraping with anti-blocking
│   ├── content_analyzer_simple.py  # Content analysis with retry logic
│   ├── document_generator.py       # Document generation with warnings
│   ├── config.py                   # Configuration settings
│   ├── models.py                   # Pydantic data models
│   ├── retry_policy.py             # Retry decorator and backoff logic
│   ├── block_detector.py           # Block detection and classification
│   ├── user_agent_pool.py          # User agent rotation
│   └── retry_logger.py             # Session-based JSON logging
├── tests/                          # Comprehensive test suite
│   ├── test_block_detector.py      # Block detection tests
│   ├── test_retry_logger.py        # Logging tests
│   ├── test_degradation.py         # Degradation tests
│   ├── test_content_analyzer.py    # Analyzer tests
│   └── test_document_generator.py  # Generator tests
├── docs/
│   └── ANTI_BLOCKING_GUIDE.md      # Detailed anti-blocking documentation
├── Output/                         # Generated reports and logs
│   ├── retry_logs/                 # Session retry logs
│   └── article_content/            # Fetched article content
└── requirements.txt                # Project dependencies
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src --cov-report=html

# Run specific test modules
python -m pytest tests/test_block_detector.py -v
python -m pytest tests/test_degradation.py -v
python -m pytest tests/test_retry_logger.py -v

# Run live integration test (requires internet)
python test_integration_live.py
```

**Test Coverage**: 76 tests covering all anti-blocking features, degradation scenarios, and core functionality.

## Acknowledgments

- Google News for providing news data
- OpenAI for language model support
- Various open-source libraries used in this project
