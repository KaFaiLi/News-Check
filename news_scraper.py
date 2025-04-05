import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from typing import List, Dict
from content_analyzer import ContentAnalyzer
from config import MAX_RETRIES, INITIAL_DELAY, MAX_ARTICLES, REQUEST_TIMEOUT, USER_AGENT, OUTPUT_DIR

class GoogleNewsScraper:
    def __init__(self, max_articles=MAX_ARTICLES, location='US', language='en'):
        self.headers = {
            'User-Agent': USER_AGENT
        }
        self.base_url = 'https://www.google.com/search'
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_DELAY
        self.max_articles = max_articles
        self.location = location
        self.language = language

    def format_date(self, date):
        """Format date to Google News format"""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.strftime('%m/%d/%Y')

    def scrape_news(self, keywords: List[str], start_date: str, end_date: str, max_articles: int = None) -> pd.DataFrame:
        """Scrape news articles based on keywords and date range
        
        Args:
            keywords: List of keywords to search for
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_articles: Maximum number of articles to fetch (overrides instance setting)
            
        Raises:
            ValueError: If dates are invalid or end_date is before start_date
        """
        # Validate dates
        try:
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
            start_idx = 0
            has_more_results = True
            
            while has_more_results and articles_found < self.max_articles:
                params = {
                    'q': keyword,
                    'tbm': 'nws',
                    'tbs': f'cdr:1,cd_min:{self.format_date(start_date)},cd_max:{self.format_date(end_date)}',
                    'num': 100,  # Request 100 articles at once
                    'start': start_idx,  # Add start parameter for pagination
                    'gl': self.location,  # Add location parameter
                    'hl': self.language   # Add language parameter
                }
                
                delay = self.initial_delay
                for retry in range(self.max_retries):
                    try:
                        page = start_idx // 100
                        print(f'Fetching page {page + 1}... ({articles_found}/{self.max_articles} articles found)')
                        response = requests.get(
                            self.base_url,
                            headers=self.headers,
                            params=params,
                            timeout=REQUEST_TIMEOUT
                        )
                        response.raise_for_status()
                        break
                    except requests.exceptions.RequestException as e:
                        if retry == self.max_retries - 1:
                            print(f'Failed to fetch page after {self.max_retries} attempts: {str(e)}')
                            has_more_results = False
                            break
                        delay *= 2
                        print(f'Retrying in {delay} seconds...')
                        time.sleep(delay)
                
                if not has_more_results:
                    break
                
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    articles = soup.find_all('div', class_='SoaBEf')
                    
                    if not articles:
                        print('No more articles found')
                        break
                    
                    for article in articles:
                        if articles_found >= self.max_articles:
                            has_more_results = False
                            break
                            
                        article_data = self._extract_article_data(article, keyword)
                        if article_data:
                            results.append(article_data)
                            articles_found += 1
                            print(f'Found article {articles_found}/{self.max_articles}: {article_data["title"][:50]}...')
                    
                    start_idx += 100  # Increment start index for next page
                    time.sleep(self.initial_delay)  # Basic rate limiting
                        
                except Exception as e:
                    print(f'Error processing page {page + 1}: {str(e)}')
                    has_more_results = False
            
            print(f'\nCompleted scraping for "{keyword}": {articles_found} articles found')
        
        # Create DataFrame from results
        df = pd.DataFrame(results)
        return df

    def _extract_article_data(self, article: BeautifulSoup, keyword: str) -> Dict:
        """Extract data from a single article"""
        title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
        link_element = article.find('a', {'class': 'WlydOe'})
        
        if not (title_element and link_element):
            return None
            
        snippet_element = article.find('div', {'class': 'GI74Re'})
        time_element = article.find('div', {'class': 'OSrXXb'})
        source_element = article.find('div', {'class': 'MgUUmf NUnG9d'})
        
        return {
            'keywords': keyword,
            'title': title_element.text.strip(),
            'url': link_element['href'],
            'snippet': snippet_element.text.strip() if snippet_element else '',
            'published_time': time_element.text.strip() if time_element else '',
            'source': source_element.text.strip() if source_element else 'Unknown'
        }

# Example usage
def main():
    # Initialize scraper with custom settings
    scraper = GoogleNewsScraper(
        max_articles=150,  # Set higher limit for total articles
        location='GB',     # Set location to Great Britain
        language='en-GB'   # Set language to British English
    )
    
    # Define search parameters
    keywords = ['artificial intelligence', 'machine learning', 'Trump']
    start_date = '2023-01-01'
    end_date = '2023-01-01'
    
    # Scrape news with custom article limit per keyword
    df = scraper.scrape_news(keywords, start_date, end_date, max_articles=50)
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save raw results to CSV and Excel
    df.to_csv(f'{OUTPUT_DIR}/raw_news_results.csv', index=False)
    df.to_excel(f'{OUTPUT_DIR}/raw_news_results.xlsx', index=False)
    print(f'\nScraped {len(df)} articles and saved raw results')
    
    # Initialize content analyzer and process articles
    analyzer = ContentAnalyzer()
    
    # Convert DataFrame to list of dictionaries for processing
    articles = df.to_dict('records')
    
    # Remove duplicates first
    unique_articles = analyzer.remove_duplicates(articles)
    print(f'Found {len(unique_articles)} unique articles after removing duplicates')
    
    # Get top 10 most relevant articles
    top_articles = analyzer.rank_articles(unique_articles)
    
    # Create DataFrame with top articles and save
    top_df = pd.DataFrame(top_articles)
    top_df.to_csv(f'{OUTPUT_DIR}/top_news_results.csv', index=False)
    top_df.to_excel(f'{OUTPUT_DIR}/top_news_results.xlsx', index=False)
    
    print(f'\nAnalyzed and saved top {len(top_articles)} most relevant articles')
    print('\nTop Articles Summary:')
    for i, article in enumerate(top_articles, 1):
        print(f'\n{i}. {article["title"]} (Relevance Score: {article["relevance_score"]:.2f})')
        print(f'   Source: {article["source"]}')


if __name__ == '__main__':
    main()