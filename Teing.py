import requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from datetime import datetime
import json

def make_google_news_request():
    # Base URL and parameters remain the same
    base_url = 'https://www.google.com/search'
    params = {
        'q': 'finance',
        'tbm': 'nws',
        'gl': 'hk',
        'hl': 'en',
        'num': 100,
        'start': 0,
        'tbs': 'qdr:d',
        'source': 'lnms'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    url = f"{base_url}?{urlencode(params)}"
    print(f"Requesting URL: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Status Code: {response.status_code}")
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('div', class_='SoaBEf')
        
        # Store parsed articles
        parsed_articles = []
        
        for article in articles:
            # Extract title with additional metadata
            title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
            title = title_element.text.strip() if title_element else 'No title'
            
            # Extract source with additional details
            source_element = article.find('div', {'class': 'MgUUmf NUnG9d'})
            source = source_element.text.strip() if source_element else 'Unknown source'
            
            # Extract published date with timezone
            time_element = article.find('div', {'class': 'OSrXXb'})
            published_date = time_element.text.strip() if time_element else 'No date'
            
            # Extract snippet with formatting
            snippet_element = article.find('div', {'class': 'GI74Re'})
            snippet = snippet_element.text.strip() if snippet_element else 'No snippet'
            
            # Extract URL and check if it's direct or redirect
            link_element = article.find('a', {'class': 'WlydOe'})
            url = link_element['href'] if link_element else 'No URL'
            
            # Extract thumbnail image if available
            thumbnail_element = article.find('img', {'class': 'tvs3Id QwxBBf'})
            thumbnail_url = thumbnail_element['src'] if thumbnail_element else None
            
            # Extract article language if available
            lang_element = article.find('div', {'class': 'LXqMce'})
            language = lang_element.text.strip() if lang_element else 'en'
            
            # Store article data with enhanced metadata
            article_data = {
                'title': title,
                'source': {
                    'name': source,
                    'language': language
                },
                'published_date': published_date,
                'snippet': snippet,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'metadata': {
                    'scrape_time': datetime.now().isoformat(),
                    'search_region': 'hk',
                    'search_language': 'en'
                }
            }
            parsed_articles.append(article_data)
            
            # Print article details in a structured way
            print("\n" + "="*50)
            print(f"Title: {title}")
            print(f"Source: {source}")
            print(f"Language: {language}")
            print(f"Published: {published_date}")
            print(f"Snippet: {snippet}")
            print(f"URL: {url}")
            if thumbnail_url:
                print(f"Thumbnail: {thumbnail_url}")
        
        # Save the full results to a JSON file
        with open('p:\\Alan\\Github\\News-Check\\news_results.json', 'w', encoding='utf-8') as f:
            json.dump(parsed_articles, f, ensure_ascii=False, indent=2)
            
        return parsed_articles
            
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None

if __name__ == "__main__":
    articles = make_google_news_request()
    if articles:
        print(f"\nTotal articles found: {len(articles)}")