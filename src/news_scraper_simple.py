import requests
import feedparser
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import html
import re
from typing import List, Dict
from content_analyzer_simple import ContentAnalyzerSimple
from document_generator import DocumentGenerator
from config import MAX_RETRIES, INITIAL_DELAY, MAX_ARTICLES, REQUEST_TIMEOUT, USER_AGENT, OUTPUT_DIR

class GoogleNewsRSSFeed:
    def __init__(self, max_articles=MAX_ARTICLES, location='US', language='en'):
        self.headers = {
            'User-Agent': USER_AGENT
        }
        self.base_url = 'https://news.google.com/rss'
        self.search_url = 'https://news.google.com/rss/search'
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_DELAY
        self.max_articles = max_articles
        self.location = location
        self.language = language

    def get_news(self, keywords: List[str], start_date: str, end_date: str, max_articles: int = None) -> pd.DataFrame:
        """Get news articles from Google News RSS feed based on keywords and date range"""
        try:
            # Validate dates
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            if end < start:
                raise ValueError('end_date must not be before start_date')
        except ValueError as e:
            if 'does not match format' in str(e):
                raise ValueError('Dates must be in YYYY-MM-DD format')
            raise
        
        results = []
        
        # Update max_articles if provided
        if max_articles is not None:
            self.max_articles = max_articles
        
        for keyword in keywords:
            print(f'\nSearching for keyword: {keyword}')
            articles_found = 0
            
            # Construct RSS feed URL with query parameter
            params = {
                'q': keyword,
                'hl': self.language,
                'gl': self.location,
                'ceid': f'{self.location}:{self.language}'
            }
            
            feed_content = None
            delay = self.initial_delay
            
            for retry in range(self.max_retries):
                try:
                    # Get RSS feed with increased timeout
                    print(f'Fetching RSS feed for keyword: {keyword} (Attempt {retry + 1}/{self.max_retries})')
                    response = requests.get(
                        self.search_url,
                        headers=self.headers,
                        params=params,
                        timeout=REQUEST_TIMEOUT * 2  # Double the timeout
                    )
                    response.raise_for_status()
                    feed_content = response.content
                    break
                except requests.exceptions.RequestException as e:
                    print(f'Request failed: {str(e)}')
                    if retry == self.max_retries - 1:
                        print(f'Failed to fetch RSS feed after {self.max_retries} attempts')
                        continue  # Skip to next keyword instead of breaking completely
                    delay *= 2
                    print(f'Retrying in {delay} seconds...')
                    time.sleep(delay)
            
            if not feed_content:
                print(f'Could not fetch content for keyword: {keyword}')
                continue
            
            # Parse RSS feed
            try:
                feed = feedparser.parse(feed_content)
                if not feed.entries:
                    print(f'No articles found for keyword: {keyword}')
                    continue
                
                # Process feed entries
                for entry in feed.entries:
                    if articles_found >= self.max_articles:
                        break
                    
                    try:
                        # Parse publication date
                        pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                        
                        # Check if article is within date range
                        if start <= pub_date <= end:
                            # Clean up article content
                            title = self._clean_html(entry.title)
                            snippet = self._clean_html(entry.description) if hasattr(entry, 'description') else ''
                            
                            # Extract source from title
                            source_match = re.search(r' - ([^-]+)$', title)
                            source = source_match.group(1).strip() if source_match else 'Unknown'
                            title = re.sub(r' - [^-]+$', '', title).strip() if source_match else title
                            
                            article_data = {
                                'keywords': keyword,
                                'title': title,
                                'url': entry.link,
                                'snippet': snippet,
                                'published_time': pub_date.isoformat(),
                                'source': source
                            }
                            
                            results.append(article_data)
                            articles_found += 1
                            print(f'Found article {articles_found}/{self.max_articles}: {title[:50]}...')
                    except Exception as e:
                        print(f"Error processing entry: {str(e)}")
                        continue
                
                print(f'\nCompleted fetching for "{keyword}": {articles_found} articles found')
                
                # Add a small delay between keywords to avoid rate limiting
                if keyword != keywords[-1]:  # Don't sleep after the last keyword
                    time.sleep(self.initial_delay)
                    
            except Exception as e:
                print(f"Error parsing feed for keyword {keyword}: {str(e)}")
                continue
        
        # Create DataFrame from results
        df = pd.DataFrame(results) if results else pd.DataFrame(columns=['keywords', 'title', 'url', 'snippet', 'published_time', 'source'])
        return df
    
    def _clean_html(self, text):
        """Clean HTML entities and tags from text"""
        # Decode HTML entities
        text = html.unescape(text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

def main():
    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Initialize RSS feed reader with custom settings
        feed_reader = GoogleNewsRSSFeed(
            max_articles=25,  # Set limit for total articles per keyword
            location='US',    # Set location 
            language='en'     # Set language
        )
        
        # Define search parameters - focused on AI, fintech and GenAI
        keywords = [
            # AI Development keywords (3 keywords)
            'artificial intelligence research',
            'machine learning breakthrough',
            'neural network development',
            
            # Fintech keywords (3 keywords)
            'fintech innovation',
            'digital banking technology',
            'blockchain finance',
            
            # GenAI Usage keywords (3 keywords)
            'generative AI',
            'ChatGPT enterprise',
            'AI content creation'
        ]
        
        # Get more recent news
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        print(f"Fetching news from {start_date} to {end_date}\n")
        print("Note: Using balanced keywords for AI Development, Fintech, and GenAI categories")
        
        # Get news with custom article limit per keyword
        df = feed_reader.get_news(keywords, start_date, end_date, max_articles=25)
        
        if df.empty:
            print("No articles were found. Please try with different keywords or date range.")
            return
        
        print("\nInitializing content analyzer...")
        # Initialize content analyzer and process articles
        analyzer = ContentAnalyzerSimple()
        
        # Convert DataFrame to list of dictionaries for processing
        articles = df.to_dict('records')
        
        print("\nRemoving duplicate articles...")
        # Remove duplicates first
        unique_articles = analyzer.remove_duplicates(articles)
        print(f'Found {len(unique_articles)} unique articles after removing duplicates')
        
        print("\nRanking and analyzing articles...")
        # Get top 10 most relevant articles
        top_articles = analyzer.rank_articles(unique_articles)
        
        # Generate topic summary
        topic_summary = analyzer.generate_topic_summary(top_articles)
        
        print("\nInitializing document generator...")
        # Initialize document generator
        doc_generator = DocumentGenerator()
        
        print("\nGenerating Word documents...")
        
        # Generate brief summary document (top 3 articles)
        brief_doc_path = doc_generator.generate_brief_summary(top_articles)
        print(f"Generated brief summary document: {brief_doc_path}")
        
        # Generate detailed report (all 10 articles)
        detailed_doc_path = doc_generator.generate_detailed_report(top_articles)
        print(f"Generated detailed report: {detailed_doc_path}")
        
        # Display category breakdown
        print(f'\nCategory Breakdown:')
        print(f'  AI Development: {topic_summary["ai_development_count"]} articles')
        print(f'  Fintech: {topic_summary["fintech_count"]} articles')
        print(f'  GenAI Usage: {topic_summary["genai_usage_count"]} articles')
        print(f'  Other: {len(top_articles) - topic_summary["ai_development_count"] - topic_summary["fintech_count"] - topic_summary["genai_usage_count"]} articles')
        
        print("\nDocuments have been generated successfully!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main() 