# News-Check

A Python-based news scraping tool that collects articles from Google News, performs sentiment analysis, and classifies financial topics using Hugging Face models.

## Features

- Scrapes news articles from Google News
- Performs sentiment analysis using FinBERT
- Classifies financial topics using BART
- Supports date range filtering
- Exports results to CSV and Excel formats

## Model Setup

This project uses two Hugging Face models that will be automatically downloaded on first use:

1. **FinBERT Model (Sentiment Analysis)**
   - Model: `ProsusAI/finbert`
   - Default storage location: `%USERPROFILE%\.cache\huggingface\hub`
   - Size: ~1.2GB

2. **BART Model (Topic Classification)**
   - Model: `facebook/bart-large-mnli`
   - Default storage location: `%USERPROFILE%\.cache\huggingface\hub`
   - Size: ~1.6GB

Note: The models will be downloaded automatically when you first run the script. Ensure you have sufficient disk space (approximately 3GB) in your user directory.

## Topic Categories

The tool classifies news articles into the following categories:
- Regulatory Compliance
- Financial Crime
- Market Risk
- Corporate Governance
- Banking
- Investment
- Insurance
- Fraud Detection
- AML
- KYC Updates

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
keywords = ['Soc Gen', 'JPM', 'Hong Kong']
start_date = '2024-01-01'
end_date = '2024-01-31'

# Scrape news articles
df = scraper.scrape_news(keywords, start_date, end_date)

# Results will be automatically saved to:
# - Output/news_results.csv
# - Output/news_results.xlsx
```

### Output Format

The scraper generates a DataFrame with the following columns:
- keywords: The search keyword used
- title: Article title
- url: Article URL
- snippet: Article description/snippet
- published_time: Publication time
- sentiment: Sentiment analysis result (positive/negative/neutral)
- topic: Classified financial topic

## Dependencies

Required packages:
- requests
- beautifulsoup4
- pandas
- transformers
- torch
- openpyxl
