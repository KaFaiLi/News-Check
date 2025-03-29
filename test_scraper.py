import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pprint import pprint

def test_google_news_scraping():
    """Test Google News scraping with various scenarios"""
    # Set up the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    base_url = 'https://www.google.com/search'
    
    # Test cases with different parameters
    test_cases = [
        {
            'name': 'Basic search',
            'params': {
                'q': 'artificial intelligence',
                'tbm': 'nws',
                'tbs': 'cdr:1,cd_min:01/01/2024,cd_max:01/01/2024'
            },
            'expected_fields': ['title', 'url', 'snippet', 'published_time']
        },
        {
            'name': 'Empty results',
            'params': {
                'q': 'nonexistentkeyword12345',
                'tbm': 'nws',
                'tbs': 'cdr:1,cd_min:01/01/1900,cd_max:01/01/1900'
            },
            'expected_fields': []
        }
    ]
    
    try:
        # Make request
        print('Fetching news articles...')
        response = requests.get(base_url, headers=headers, params=test_cases[0]['params'])
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all news articles
        articles = soup.find_all('div', class_='SoaBEf')
        print(f'\nFound {len(articles)} articles\n')
        
        # Test extraction of various elements from each article
        for i, article in enumerate(articles, 1):
            print(f'\nArticle {i}:')
            print('-' * 50)
            
            # Store all possible data points
            article_data = {}
            
            # 1. Title (multiple possible class names)
            title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
            if title_element:
                article_data['title'] = title_element.text.strip()
                print('Title found:', article_data['title'])
            
            # 2. URL
            link_element = article.find('a', {'class': 'WlydOe'})
            if link_element:
                article_data['url'] = link_element['href']
                print('URL found:', article_data['url'])
            
            # 3. Source/Publisher
            source_element = article.find('div', {'class': 'UPmit'})
            if source_element:
                article_data['source'] = source_element.text.strip()
                print('Source found:', article_data['source'])
            
            # 4. Snippet/Description
            snippet_element = article.find('div', {'class': 'GI74Re'})
            if snippet_element:
                article_data['snippet'] = snippet_element.text.strip()
                print('Snippet found:', article_data['snippet'])
            
            # 5. Time/Date
            time_element = article.find('div', {'class': 'OSrXXb'})
            if time_element:
                article_data['time'] = time_element.text.strip()
                print('Time found:', article_data['time'])
            
            # 6. Thumbnail Image
            img_element = article.find('img', {'class': 'tvs3Id'})
            if img_element and 'src' in img_element.attrs:
                article_data['thumbnail_url'] = img_element['src']
                print('Thumbnail URL found:', article_data['thumbnail_url'])
            
            # 7. Additional metadata (if any)
            metadata_element = article.find('div', {'class': 'OSrXXb'})
            if metadata_element:
                article_data['metadata'] = metadata_element.text.strip()
                print('Additional metadata found:', article_data['metadata'])
            
            # Print raw HTML for analysis
            print('\nRaw HTML structure:')
            print(article.prettify()[:500] + '...' if len(article.prettify()) > 500 else article.prettify())
            
            print('\nExtracted Data Dictionary:')
            pprint(article_data)
            
            print('\nFound HTML classes:')
            all_classes = set()
            for element in article.find_all(class_=True):
                all_classes.update(element['class'])
            pprint(list(all_classes))
            
    except Exception as e:
        print(f'Error occurred: {str(e)}')

def test_html_structure_changes():
    """Test handling of potential HTML structure changes"""
    print('\nTesting HTML structure changes...')
    
    # Test with malformed HTML
    malformed_html = "<div><div class='SoaBEf'><div>Test Title</div></div>"
    soup = BeautifulSoup(malformed_html, 'html.parser')
    
    # Test extraction with missing elements
    articles = soup.find_all('div', class_='SoaBEf')
    for article in articles:
        title_element = article.find('div', {'class': ['n0jPhd', 'MBeuO', 'ynAwRc', 'PYlxcf']})
        assert title_element is None, "Should handle missing title elements"
    
    print('HTML structure change tests passed')


def test_error_handling():
    """Test error handling scenarios"""
    print('\nTesting error handling...')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Test with invalid URL
    try:
        response = requests.get('https://invalid.url', headers=headers, timeout=5)
        assert False, "Should raise exception for invalid URL"
    except requests.exceptions.RequestException:
        pass
    
    print('Error handling tests passed')


if __name__ == '__main__':
    print('Starting comprehensive Google News scraping tests...')
    test_google_news_scraping()
    test_html_structure_changes()
    test_error_handling()
    print('\nAll tests completed!')