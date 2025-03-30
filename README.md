# Google News Scraper

A Python-based web scraper for Google News that includes sentiment analysis using BERT.

## Features

- Search news articles by multiple keywords
- Filter articles by date range
- Extract comprehensive article information:
  - Title
  - URL
  - Snippet/Description
  - Published Time
  - Source
- Sentiment analysis using BERT model
- Automatic pagination handling
- Export results to CSV and Excel formats
- Built-in rate limiting and retry mechanism
- Comprehensive error handling

## Installation

1. Clone the repository or download the source code
2. Install the required dependencies:

```bash
pip install -r requirements.txt
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

### Sentiment Analysis

The scraper includes BERT-based sentiment analysis for each article title. The sentiment is classified as:
- Positive: score > 0.6 (3+ stars out of 5)
- Negative: score < 0.4 (2 or fewer stars out of 5)
- Neutral: score between 0.4 and 0.6

The sentiment analysis results are included in the output DataFrame and exported files.

## Output Format

The scraper generates a DataFrame with the following columns:
- keywords: The search keyword used
- title: Article title
- url: Article URL
- snippet: Article description/snippet
- published_time: Publication time
- sentiment: Sentiment analysis result (positive/negative/neutral)

## Error Handling

The scraper includes:
- Automatic retry mechanism with exponential backoff
- Rate limiting to avoid overloading the server
- Comprehensive error reporting
- Graceful handling of missing data

## Dependencies

See requirements.txt for detailed version information:
- requests
- beautifulsoup4
- pandas
- transformers
- torch
- openpyxl
