import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
from transformers import pipeline

class GoogleNewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = 'https://www.google.com/search'

    def format_date(self, date):
        """Format date to Google News format"""
        return date.strftime('%m/%d/%Y')

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = 'https://www.google.com/search'
        # Initialize FinBERT sentiment analyzer and financial topic classifier
        self.sentiment_analyzer = pipeline('sentiment-analysis', model='ProsusAI/finbert')
        self.topic_classifier = pipeline('zero-shot-classification', model='facebook/bart-large-mnli')
        self.topic_categories = [
            'Regulatory Compliance', 'Financial Crime', 'Market Risk', 'Corporate Governance',
            'Banking', 'Investment', 'Insurance', 'Fraud Detection', 'AML', 'KYC Updates'
        ]

    def analyze_sentiment(self, text):
        """Analyze sentiment of text using BERT"""
        result = self.sentiment_analyzer(text)[0]
        label = result['label'].lower()
        
        # FinBERT returns 'positive', 'negative', or 'neutral' directly
        return label
            
    def analyze_topic(self, title, snippet):
        """Analyze topic of the article using zero-shot classification"""
        # Combine title and snippet for better topic analysis
        full_text = f"{title}. {snippet}"
        result = self.topic_classifier(
            full_text,
            candidate_labels=self.topic_categories,
            multi_label=False
        )
        return result['labels'][0]  # Return the most likely topic

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
                            
                            # Analyze sentiment and topic
                            sentiment = self.analyze_sentiment(title)
                            topic = self.analyze_topic(title, snippet)
                            
                            print(f'Found article: {title[:50]}... (Sentiment: {sentiment}, Topic: {topic})')
                            
                            results.append({
                                'keywords': keyword,
                                'title': title,
                                'url': url,
                                'snippet': snippet,
                                'published_time': published_time,
                                'sentiment': sentiment,
                                'topic': topic
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
        df = pd.DataFrame(results)
        
        # Create a directory for output if it doesn't exist
        import os
        os.makedirs('Output', exist_ok=True)
        
        return df

# Example usage
def main():
    # Initialize scraper
    scraper = GoogleNewsScraper()
    
    # Define search parameters
    keywords = ['Soc Gen', 'JPM', 'Hong Kong']
    start_date = '2025-01-01'
    end_date = '2025-01-01'
    
    # Scrape news
    df = scraper.scrape_news(keywords, start_date, end_date)
    
    # Save to CSV and Excel with sentiment analysis results
    df.to_csv('Output/news_results.csv', index=False)
    df.to_excel('Output/news_results.xlsx', index=False)
    
    # Print summary of sentiment analysis
    sentiment_counts = df['sentiment'].value_counts()
    print(f'\nScraped {len(df)} articles and saved to news_results.csv')
    print('\nSentiment Analysis Summary:')
    print(f'Positive articles: {sentiment_counts.get("positive", 0)}')
    print(f'Negative articles: {sentiment_counts.get("negative", 0)}')
    
    # Print summary of topics
    topic_counts = df['topic'].value_counts()
    print('\nTopic Distribution:')
    for topic, count in topic_counts.items():
        print(f'{topic}: {count} articles')
    print(f'Neutral articles: {sentiment_counts.get("neutral", 0)}')

if __name__ == '__main__':
    main()