"""Configuration settings for the News Scraper application."""

# OpenAI API settings
OPENAI_API_KEY = ''  # Replace with your actual OpenAI API key
OPENAI_API_BASE = 'https://openrouter.ai/api/v1'  # Replace with your actual OpenAI API base URL

# Content Analysis settings
USE_LLM = True  # Set to True to use the LLM for content analysis, False for keyword-only mode
LLM_THRESHOLD = 0.1  # Minimum keyword relevance score to trigger LLM analysis

# RSS Feed settings
MAX_RETRIES = 5  # Maximum number of retry attempts for failed requests
INITIAL_DELAY = 1  # Initial delay between requests in seconds
MAX_ARTICLES = 50  # Maximum number of articles to fetch per keyword

# Request settings
REQUEST_TIMEOUT = 30  # Request timeout in seconds
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Output settings
OUTPUT_DIR = 'Output'  # Directory for saving scraped results