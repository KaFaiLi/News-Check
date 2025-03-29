# Google News Scraper

A Python-based web scraper for extracting news articles from Google News. This tool allows you to search for news articles based on keywords and date ranges, with built-in pagination support and robust error handling.

## Features

- Search news articles by multiple keywords
- Filter articles by date range
- Extract comprehensive article information:
  - Title
  - URL
  - Snippet/Description
  - Published Time
- Automatic pagination handling
- Export results to CSV and Excel formats
- Built-in rate limiting and retry mechanism
- Comprehensive error handling
- Extensive test coverage

## Installation

1. Clone the repository or download the source code
2. Install the required dependencies:

```bash
pip install requests beautifulsoup4 pandas
```

## Usage

### Basic Usage

```python
from news_scraper import GoogleNewsScraper

# Initialize the scraper
scraper = GoogleNewsScraper()

# Define search parameters
keywords = ['artificial intelligence', 'machine learning']
start_date = '2024-01-01'
end_date = '2024-01-01'

# Scrape news articles
df = scraper.scrape_news(keywords, start_date, end_date)

# Save results
df.to_csv('news_results.csv', index=False)
df.to_excel('news_results.xlsx', index=False)
```

### Advanced Configuration

You can customize the scraping behavior with additional parameters:

```python
df = scraper.scrape_news(
    keywords=['AI', 'ML'],
    start_date='2024-01-01',
    end_date='2024-01-01',
    max_retries=3,      # Maximum number of retry attempts
    initial_delay=2     # Initial delay between requests (seconds)
)
```

## Testing

The project includes comprehensive test coverage:

```bash
python test_scraper.py
```

Test cases include:
- Basic news article scraping
- Empty results handling
- HTML structure changes
- Error handling scenarios

## Important Notes

1. **Rate Limiting**: The scraper implements exponential backoff to avoid overwhelming Google's servers. Adjust the `initial_delay` parameter if needed.

2. **HTML Structure**: The scraper is designed to handle various HTML structures and class names that Google News might use. Test cases ensure robustness against structure changes.

3. **Error Handling**: The scraper includes comprehensive error handling for:
   - Network issues
   - Invalid URLs
   - Rate limiting
   - Malformed HTML
   - Missing data fields

## Output Format

The scraper returns a pandas DataFrame with the following columns:
- keywords: Search term used
- title: Article title
- url: Article URL
- snippet: Article description/snippet
- published_time: Publication time/date
# News-Check
