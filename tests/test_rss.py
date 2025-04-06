import requests
import feedparser
import time
from datetime import datetime

# Basic test configuration
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
SEARCH_URL = 'https://news.google.com/rss/search'
TIMEOUT = 10
KEYWORD = 'artificial intelligence'

def test_rss_feed():
    print(f"Testing RSS feed for keyword: {KEYWORD}")
    
    # Prepare request params
    params = {
        'q': KEYWORD,
        'hl': 'en',
        'gl': 'US',
        'ceid': 'US:en'
    }
    
    headers = {
        'User-Agent': USER_AGENT
    }
    
    try:
        # Make the request
        print("Fetching RSS feed...")
        response = requests.get(
            SEARCH_URL,
            headers=headers,
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        # Parse the feed
        print("Parsing feed content...")
        feed = feedparser.parse(response.content)
        
        # Show feed info
        if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
            print(f"\nFeed title: {feed.feed.title}")
        else:
            print("\nCouldn't find feed title")
        
        # Count entries
        num_entries = len(feed.entries) if hasattr(feed, 'entries') else 0
        print(f"Found {num_entries} articles")
        
        # Show first 3 entries
        if num_entries > 0:
            print("\nFirst 3 articles:")
            for i, entry in enumerate(feed.entries[:3]):
                print(f"\n{i+1}. {entry.title}")
                print(f"   Link: {entry.link}")
                print(f"   Published: {entry.published}")
                if hasattr(entry, 'description'):
                    desc = entry.description[:100] + "..." if len(entry.description) > 100 else entry.description
                    print(f"   Description: {desc}")
        else:
            print("No articles found")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_rss_feed() 