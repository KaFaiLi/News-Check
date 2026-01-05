"""Live integration test for scraper with retry functionality."""

import sys
from datetime import datetime, timedelta
from src.news_scraper_simple import GoogleNewsScraper

def test_live_scraping():
    """Test scraper against live Google News with retry logging."""
    print("=" * 80)
    print("LIVE INTEGRATION TEST - News Scraper with Anti-Blocking")
    print("=" * 80)
    
    # Initialize scraper
    scraper = GoogleNewsScraper(max_articles_per_keyword=5, location='US', language='en')
    
    # Test with a single keyword for quick validation
    keywords = ['artificial intelligence']
    
    # Date range: last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"\nTest Parameters:")
    print(f"  Keywords: {keywords}")
    print(f"  Date Range: {start_date.date()} to {end_date.date()}")
    print(f"  Max Articles: 5 per keyword")
    print("\n" + "-" * 80 + "\n")
    
    try:
        # Run scraper
        results = scraper.get_news(
            keywords=keywords,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            max_articles=5
        )
        
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        
        if not results.empty:
            print(f"✓ SUCCESS: Retrieved {len(results)} articles")
            print(f"\nSample Articles:")
            for idx, row in results.head(3).iterrows():
                print(f"\n  [{idx+1}] {row['title'][:80]}...")
                print(f"      URL: {row['url'][:60]}...")
                print(f"      Source: {row['source']}")
                print(f"      Published: {row['published_time']}")
            
            # Check for retry logs
            import os
            retry_log_dir = "Output/retry_logs"
            if os.path.exists(retry_log_dir):
                log_files = [f for f in os.listdir(retry_log_dir) if f.endswith('.json')]
                if log_files:
                    print(f"\n✓ Retry logs generated: {len(log_files)} file(s)")
                    print(f"  Latest: {retry_log_dir}/{log_files[-1]}")
            
            return True
        else:
            print("✗ FAILED: No articles retrieved")
            return False
            
    except Exception as e:
        print(f"\n✗ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_live_scraping()
    sys.exit(0 if success else 1)
