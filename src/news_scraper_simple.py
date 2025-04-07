import requests
# import feedparser # No longer needed for direct scraping
import pandas as pd
from datetime import datetime, timedelta, timezone # Added timezone
import time
import os
import html
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus # For URL encoding keywords

from bs4 import BeautifulSoup # Import BeautifulSoup

from src.content_analyzer_simple import ContentAnalyzerSimple
from src.document_generator import DocumentGenerator
from src.config import MAX_RETRIES, INITIAL_DELAY, REQUEST_TIMEOUT, USER_AGENT, OUTPUT_DIR

# Rename class to reflect scraping method
class GoogleNewsScraper:
    def __init__(self, max_articles_per_keyword, location='US', language='en'):
        self.headers = {
            'User-Agent': USER_AGENT,
            # Might need more headers to mimic a real browser
            'Accept-Language': f'{language}-{location}, {language};q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        }
        # Target the standard Google Search endpoint for News
        self.search_url_base = 'https://www.google.com/search' # Changed from news.google.com
        self.max_retries = MAX_RETRIES
        self.initial_delay = INITIAL_DELAY
        self.max_articles_per_keyword = max_articles_per_keyword # Limit per keyword
        self.location = location
        self.language = language
        self.max_results_per_request = 100  # Maximum allowed by Google
        self.default_results_per_request = 10  # Default for smaller requests

        print("--- INFO ---")
        print("Using direct HTML scraping via google.com/search?tbm=nws.")
        print("This method can be unreliable due to:")
        print("  1. Frequent changes in Google's HTML structure (selectors may break).")
        print("  2. Potential for CAPTCHAs or IP blocks.")
        print("------------")

    # Helper function to format date for Google 'tbs' parameter
    def _format_date_for_tbs(self, date_str: str) -> str:
        """Formats YYYY-MM-DD date to MM/DD/YYYY for tbs parameter."""
        try:
            dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return dt_obj.strftime('%m/%d/%Y')
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")

    def _parse_relative_time(self, time_str: str) -> Optional[datetime]:
        """Parses relative time strings like '1 hour ago', '2 days ago'."""
        if not time_str:
            return None
        time_str = time_str.lower().strip()
        now = datetime.now(timezone.utc) # Use timezone-aware datetime

        try:
            if 'yesterday' in time_str:
                return now - timedelta(days=1)
            if 'hour' in time_str:
                hours = int(re.search(r'(\d+)\s+hour', time_str).group(1))
                return now - timedelta(hours=hours)
            if 'day' in time_str:
                days = int(re.search(r'(\d+)\s+day', time_str).group(1))
                return now - timedelta(days=days)
            if 'minute' in time_str:
                 minutes = int(re.search(r'(\d+)\s+minute', time_str).group(1))
                 return now - timedelta(minutes=minutes)
            # Add more cases if needed (weeks, months - less precise)
            # Try parsing as absolute date if format matches Mmm D, YYYY or similar
            try:
                # Example: 'Dec 5, 2023' - adjust format as needed
                return datetime.strptime(time_str, '%b %d, %Y').replace(tzinfo=timezone.utc)
            except ValueError:
                pass # Not an absolute date we handle

        except Exception as e:
            # print(f"Debug: Could not parse relative time '{time_str}': {e}") # Optional debug
            pass # Ignore if parsing fails

        return None # Return None if format is unrecognized

    def _get_results_per_request(self, target_articles: int) -> int:
        """Determine optimal number of results per request based on target articles."""
        if target_articles <= 10:
            return 10  # Use minimum for small requests
        elif target_articles <= 50:
            return 50  # Medium batch size
        else:
            return 100  # Maximum for large requests (Google's limit)

    # Overhauled get_news method
    def get_news(self, keywords: List[str], start_date: str, end_date: str, max_articles: Optional[int] = None) -> pd.DataFrame:
        """Get news articles by scraping Google Search (News tab) HTML results."""
        print("\n--- Starting HTML Scraping (google.com/search) ---")
        try:
            f_start_date = self._format_date_for_tbs(start_date)
            f_end_date = self._format_date_for_tbs(end_date)
        except ValueError as e:
             print(f"Error: {e}")
             return pd.DataFrame() # Return empty DataFrame on invalid date
        
        results = []
        total_articles_target = max_articles if max_articles is not None else float('inf')
        articles_collected_total = 0
        
        try:
            for keyword in keywords:
                if articles_collected_total >= total_articles_target:
                     print("Reached overall article limit. Stopping search.")
                     break

                print(f'\nSearching for keyword: "{keyword}"')
                articles_found_for_keyword = 0
                page = 0
                
                # Calculate remaining articles needed for this keyword
                remaining_articles = min(
                    self.max_articles_per_keyword,
                    total_articles_target - articles_collected_total
                )
                
                while articles_found_for_keyword < remaining_articles:
                    # Determine results per request for this page
                    results_per_request = self._get_results_per_request(remaining_articles - articles_found_for_keyword)
                    
                    # Construct search parameters for this page
                    params = {
                        'q': keyword,
                        'tbm': 'nws',
                        'hl': self.language,
                        'gl': self.location,
                        'tbs': f'cdr:1,cd_min:{f_start_date},cd_max:{f_end_date}',
                        'start': page * 100,  # Google uses 100 as the base unit for pagination
                        'num': results_per_request
                    }

                    try:
                        print(f'Fetching page {page + 1} for keyword "{keyword}" ({articles_found_for_keyword}/{remaining_articles} articles found)')
                        response = requests.get(
                            self.search_url_base,
                            params=params,
                            headers=self.headers,
                            timeout=REQUEST_TIMEOUT
                        )
                        
                        if response.status_code != 200:
                            print(f"Warning: Received status code {response.status_code}")
                            if "captcha" in response.text.lower():
                                print("Error: CAPTCHA detected. Cannot proceed with scraping.")
                                break
                            response.raise_for_status()

                        print("HTML fetched successfully.")
                        soup = BeautifulSoup(response.text, 'html.parser')
                        articles = soup.select('div.SoaBEf')
                        
                        if not articles:
                            print("No more articles found on this page.")
                            break

                        print(f"Found {len(articles)} articles on page.")
                        articles_processed = 0

                        for article in articles:
                            if articles_found_for_keyword >= remaining_articles:
                                print(f"Reached target of {remaining_articles} articles for this keyword.")
                                break
                            if articles_collected_total >= total_articles_target:
                                print("Reached overall article limit.")
                                break

                            try:
                                title_element = article.select_one('div.n0jPhd.ynAwRc.MBeuO.nDgy9d')
                                if not title_element:
                                    continue

                                title = title_element.get_text(strip=True)
                                source_element = article.select_one('div.MgUUmf.NUnG9d')
                                source = source_element.get_text(strip=True) if source_element else "Unknown Source"
                                snippet_element = article.select_one('div.GI74Re.nDgy9d')
                                snippet = snippet_element.get_text(strip=True) if snippet_element else ""
                                link_element = article.select_one('a[href]')
                                link = link_element['href'] if link_element else "#"
                                if link.startswith('/url?'):
                                    link = f"https://www.google.com{link}"

                                spans = article.find_all('span', class_='')
                                pub_time_str = spans[-1].get_text(strip=True) if spans else "Unknown Time"
                                pub_time_obj = self._parse_relative_time(pub_time_str)
                                pub_time = pub_time_obj.isoformat() if pub_time_obj else pub_time_str

                                # Store article data with HTML for thumbnail extraction
                                article_data = {
                                    'keywords': keyword,
                                    'title': title,
                                    'url': link,
                                    'snippet': snippet,
                                    'published_time': pub_time,
                                    'source': source
                                }

                                results.append(article_data)
                                articles_found_for_keyword += 1
                                articles_collected_total += 1
                                articles_processed += 1
                                print(f"Found article {articles_collected_total}/{total_articles_target}: {title[:60]}...")

                            except Exception as e:
                                print(f"Error processing article: {str(e)}")
                                continue

                        print(f'Found {articles_processed} articles for keyword "{keyword}" on page {page + 1}')
                        
                        if articles_processed < results_per_request:
                            print("No more results available.")
                            break
                            
                        page += 1
                        time.sleep(self.initial_delay)

                    except requests.exceptions.RequestException as e:
                        print(f'Request failed: {str(e)}')
                        if page >= self.max_retries:
                            print(f'Failed to fetch page after {self.max_retries} attempts.')
                            break
                        time.sleep(self.initial_delay * (2 ** page))
                        continue
                    except Exception as e:
                        print(f'Unexpected error: {str(e)}')
                        break

                if keyword != keywords[-1] and articles_collected_total < total_articles_target:
                    time.sleep(self.initial_delay)

        except Exception as e:
            print(f"Error in get_news: {str(e)}")
            return pd.DataFrame()

        print(f"\n--- HTML Scraping Finished ---")
        print(f"Collected a total of {len(results)} articles.")

        return pd.DataFrame(results) if results else pd.DataFrame(
            columns=['keywords', 'title', 'url', 'snippet', 'published_time', 'source']
        )
