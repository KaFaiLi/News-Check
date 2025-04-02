import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from typing import List, Dict
from content_analyzer import ContentAnalyzer

class GoogleNewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = 'https://www.google.com/search'
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.initial_delay = int(os.getenv('INITIAL_DELAY', '2'))
        self.max_articles = int(os.getenv('MAX_ARTICLES', '100'))  # Make max_articles configurable

    def format_date(self, date):
        """Format date to Google News format"""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.strftime('%m/%d/%Y')

    def scrape_news(self, keywords: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Scrape news articles based on keywords and date range"""
        results = []
        
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
                    'start': start_idx  # Add start parameter for pagination
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
                            timeout=10
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
            
            df.to_excel('Output/raw_news_results.xlsx', index=False)
            print(f'\nScraped {len(df)} articles and saved raw results')
        return pd.DataFrame(results)

    def _extract_article_data(self, article: BeautifulSoup, keyword: str) -> Dict:
        """Extract data from a single article"""
        title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
        link_element = article.find('a', {'class': 'WlydOe'})
        
        if not (title_element and link_element):
            return None
            
        snippet_element = article.find('div', {'class': 'GI74Re'})
        time_element = article.find('div', {'class': 'OSrXXb'})
        source_element = article.find('div', {'class': 'UPmit'})
        
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
    # Initialize scraper
    scraper = GoogleNewsScraper()
    
    # Define search parameters
    keywords = ['artificial intelligence', 'machine learning', 'Trump']
    start_date = '2023-01-01'
    end_date = '2023-01-01'
    
    # Scrape news
    df = scraper.scrape_news(keywords, start_date, end_date)
    
    # Create output directory if it doesn't exist
    os.makedirs('Output', exist_ok=True)
    
    # Save raw results to CSV and Excel
    df.to_csv('Output/raw_news_results.csv', index=False)
    df.to_excel('Output/raw_news_results.xlsx', index=False)
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
    top_df.to_csv('Output/top_news_results.csv', index=False)
    top_df.to_excel('Output/top_news_results.xlsx', index=False)
    
    print(f'\nAnalyzed and saved top {len(top_articles)} most relevant articles')
    print('\nTop Articles Summary:')
    for i, article in enumerate(top_articles, 1):
        print(f'\n{i}. {article["title"]} (Relevance Score: {article["relevance_score"]:.2f})')
        print(f'   Source: {article["source"]}')


if __name__ == '__main__':
    main()