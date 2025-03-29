import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time

class GoogleNewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = 'https://www.google.com/search'

    def format_date(self, date):
        """Format date to Google News format"""
        return date.strftime('%m/%d/%Y')

    def scrape_news(self, keywords, start_date, end_date, max_retries=3, initial_delay=2):
        """Scrape news articles based on keywords and date range"""
        # Convert string dates to datetime objects if they're strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        # Initialize results list
        results = []
        
        # Process each keyword separately
        for keyword in keywords:
            print(f'\nSearching for keyword: {keyword}')
            page = 0
            has_more_results = True
            
            # Use single keyword as query
            query = keyword
            
            while has_more_results:
                # Calculate start index for pagination
                start_idx = page * 10
            
                # Construct search parameters
                params = {
                    'q': query,
                    'tbm': 'nws',  # News search
                    'tbs': f'cdr:1,cd_min:{self.format_date(start_date)},cd_max:{self.format_date(end_date)}',
                    'start': start_idx
                }
                
                try:
                    # Make request
                    print(f'Fetching page {page + 1}...')
                    response = requests.get(self.base_url, headers=self.headers, params=params)
                    response.raise_for_status()
                    
                    # Debug information
                    print(f'Response status code: {response.status_code}')
                    if response.status_code != 200:
                        print(f'Response text: {response.text}')
                        print('Stopping due to non-200 status code')
                        break
                    
                    # Parse HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find all news articles
                    articles = soup.find_all('div', class_='SoaBEf')
                    article_count = len(articles)
                    print(f'Found {article_count} articles on page {page + 1}')
                    
                    if not articles:
                        print('No articles found on this page. Stopping search.')
                        has_more_results = False
                        break
                    
                    # Extract information from each article
                    for article in articles:
                        title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
                        link_element = article.find('a', {'class': 'WlydOe'})
                        source_element = article.find('div', {'class': 'UPmit'})
                        
                        if title_element and link_element:
                            title = title_element.text.strip()
                            url = link_element['href']
                            
                            # Extract snippet
                            snippet_element = article.find('div', {'class': 'GI74Re'})
                            snippet = snippet_element.text.strip() if snippet_element else ''
                            
                            # Extract time/date
                            time_element = article.find('div', {'class': 'OSrXXb'})
                            published_time = time_element.text.strip() if time_element else ''
                            
                            print(f'Found article: {title[:50]}...')
                            
                            results.append({
                                'keywords': keyword,
                                'title': title,
                                'url': url,
                                'snippet': snippet,
                                'published_time': published_time
                            })
                    
                    # Check if we should continue to the next page
                    if article_count < 10:
                        print('Found fewer than 10 articles. No more pages to check.')
                        has_more_results = False
                    else:
                        # If we found exactly 10 articles, we need to check the next page
                        page += 1
                    
                    # Implement exponential backoff
                    delay = initial_delay
                    retries = 0
                    while retries < max_retries:
                        try:
                            time.sleep(delay)
                            break
                        except requests.exceptions.RequestException:
                            retries += 1
                            delay *= 2
                            print(f'Retrying page {page + 1} (attempt {retries + 1}/{max_retries})')
                            if retries == max_retries:
                                print(f'Failed to fetch page {page + 1} after {max_retries} attempts')
                                has_more_results = False
                                break
                
                except Exception as e:
                    print(f'Error occurred on page {page + 1}: {str(e)}')
                    has_more_results = False
                    break
        
        # Convert results to DataFrame
        return pd.DataFrame(results)

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
    
    # Save to CSV
    df.to_csv('Output/news_results.csv', index=False)
    df.to_excel('Output/news_results.xlsx', index=False)
    print(f'Scraped {len(df)} articles and saved to news_results.csv')

if __name__ == '__main__':
    main()