"""Configuration settings for the News Scraper application."""

# OpenAI API settings
OPENAI_API_KEY = 'your-api-key-here'  # Replace with your actual OpenAI API key
OPENAI_API_BASE = 'your-api-base-url-here'  # Replace with your actual OpenAI API base URL

# Scraping settings
MAX_RETRIES = 3  # Maximum number of retry attempts for failed requests
INITIAL_DELAY = 2  # Initial delay between requests in seconds
MAX_ARTICLES = 100  # Maximum number of articles to scrape per keyword

# Request settings
REQUEST_TIMEOUT = 10  # Request timeout in seconds
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Output settings
OUTPUT_DIR = 'Output'  # Directory for saving scraped results