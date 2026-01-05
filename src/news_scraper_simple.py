import requests
# import feedparser # No longer needed for direct scraping
import pandas as pd
from datetime import datetime, timedelta, timezone # Added timezone
import time
import os
import html
import re
import random  # For random delays
import logging  # For comprehensive logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus # For URL encoding keywords

from bs4 import BeautifulSoup # Import BeautifulSoup

from src.content_analyzer_simple import ContentAnalyzerSimple
from src.document_generator import DocumentGenerator
from src.config import MAX_RETRIES, INITIAL_DELAY, REQUEST_TIMEOUT, USER_AGENT, OUTPUT_DIR, RANDOM_DELAY_RANGE
from src.config import ENABLE_GRACEFUL_DEGRADATION, MIN_SUCCESS_THRESHOLD, MAX_CONSECUTIVE_FAILURES, COLLECT_PARTIAL_RESULTS
from src.retry_policy import retry_with_backoff
from src.user_agent_pool import user_agent_pool
from src.retry_logger import retry_logger
from src.models import DegradationStatus

# Module-level logger
logger = logging.getLogger(__name__)

# Rename class to reflect scraping method
class GoogleNewsScraper:
    def __init__(self, max_articles_per_keyword, location='US', language='en'):
        self.headers = {
            # User-Agent will be dynamically rotated via user_agent_pool
            'User-Agent': user_agent_pool.get_next(),
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
        
        # Degradation tracking (Phase 5: Graceful Degradation)
        self.degradation_status = DegradationStatus()
        self.enable_graceful_degradation = ENABLE_GRACEFUL_DEGRADATION
        self.min_success_threshold = MIN_SUCCESS_THRESHOLD
        self.max_consecutive_failures = MAX_CONSECUTIVE_FAILURES

        print("--- INFO ---")
        print("Using direct HTML scraping via google.com/search?tbm=nws.")
        print("This method can be unreliable due to:")
        print("  1. Frequent changes in Google's HTML structure (selectors may break).")
        print("  2. Potential for CAPTCHAs or IP blocks.")
        print("  3. Now includes intelligent retry with exponential backoff and user agent rotation.")
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
        """Parses relative time strings like '1 hour ago', '2 days ago', or absolute dates."""
        if not time_str or time_str == 'Unknown Time':
            return None
            
        time_str = time_str.lower().strip()
        now = datetime.now(timezone.utc)

        try:
            # Handle relative time formats
            if 'ago' in time_str:
                if 'hour' in time_str:
                    hours = int(''.join(filter(str.isdigit, time_str)))
                    return now - timedelta(hours=hours)
                elif 'day' in time_str:
                    days = int(''.join(filter(str.isdigit, time_str)))
                    return now - timedelta(days=days)
                elif 'minute' in time_str:
                    minutes = int(''.join(filter(str.isdigit, time_str)))
                    return now - timedelta(minutes=minutes)
                elif 'week' in time_str:
                    weeks = int(''.join(filter(str.isdigit, time_str)))
                    return now - timedelta(weeks=weeks)
                elif 'month' in time_str:
                    months = int(''.join(filter(str.isdigit, time_str)))
                    # Approximate months as 30 days
                    return now - timedelta(days=30 * months)
            elif 'yesterday' in time_str:
                return now - timedelta(days=1)
            elif 'today' in time_str:
                return now
            
            # Try common absolute date formats
            date_formats = [
                '%b %d, %Y',       # Dec 25, 2023
                '%B %d, %Y',       # December 25, 2023
                '%Y-%m-%d',        # 2023-12-25
                '%d %b %Y',        # 25 Dec 2023
                '%d %B %Y',        # 25 December 2023
                '%Y/%m/%d',        # 2023/12/25
                '%d/%m/%Y',        # 25/12/2023
                '%m/%d/%Y',        # 12/25/2023
                '%b %d',           # Dec 25 (current year)
                '%B %d'            # December 25 (current year)
            ]
            
            for date_format in date_formats:
                try:
                    # For formats without year, add the current year
                    if '%Y' not in date_format:
                        parsed_date = datetime.strptime(time_str, date_format).replace(year=now.year)
                    else:
                        parsed_date = datetime.strptime(time_str, date_format)
                    return parsed_date.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

            # If we get here, no format matched
            return None

        except Exception as e:
            print(f"Debug: Could not parse time '{time_str}': {e}")
            return None

    def _get_results_per_request(self, target_articles: int) -> int:
        """Determine optimal number of results per request based on target articles."""
        if target_articles <= 10:
            return 10  # Use minimum for small requests
        elif target_articles <= 50:
            return 50  # Medium batch size
        else:
            return 100  # Maximum for large requests (Google's limit)

    @retry_with_backoff(max_attempts=MAX_RETRIES)
    def _fetch_page(self, url: str, params: Dict, headers: Dict) -> requests.Response:
        """Fetch a page with retry logic and intelligent blocking detection.
        
        Args:
            url: Base URL to fetch
            params: Query parameters
            headers: Request headers
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        # Rotate user agent for this request
        headers['User-Agent'] = user_agent_pool.get_next()
        
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        
        # Check for CAPTCHA in response
        if "captcha" in response.text.lower():
            print("Error: CAPTCHA detected. Cannot proceed with scraping.")
            # Raise exception to trigger retry with different user agent
            response.raise_for_status()  
        
        # Raise for bad status codes (will trigger retry)
        response.raise_for_status()
        
        return response

    # Overhauled get_news method
    def get_news(self, keywords: List[str], start_date: str, end_date: str, max_articles: Optional[int] = None) -> pd.DataFrame:
        """Get news articles by scraping Google Search (News tab) HTML results."""
        print("\n--- Starting HTML Scraping (google.com/search) ---")
        
        # Log retry session start
        logger.info(f"Retry session started: {retry_logger.session_id}")
        
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
                        
                        # Use _fetch_page with retry logic
                        response = self._fetch_page(
                            url=self.search_url_base,
                            params=params,
                            headers=self.headers.copy()  # Pass copy to allow header modification
                        )
                        
                        # Track successful fetch
                        self.degradation_status.update_success()
                        
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
                        
                        # Add random delay between page requests (anti-bot timing)
                        delay = random.uniform(*RANDOM_DELAY_RANGE)
                        time.sleep(delay)

                    except requests.exceptions.RequestException as e:
                        error_msg = f'Request failed after retries for keyword "{keyword}": {str(e)}'
                        print(error_msg)
                        logger.error(error_msg)
                        
                        # Track failed fetch and check degradation threshold
                        self.degradation_status.update_failure(error_msg)
                        
                        if self.enable_graceful_degradation:
                            is_degraded = self.degradation_status.check_degradation_threshold(
                                self.min_success_threshold,
                                self.max_consecutive_failures
                            )
                            
                            if is_degraded:
                                warning = f"Entering degraded mode: {self.degradation_status.consecutive_failures} consecutive failures"
                                print(f"⚠️  {warning}")
                                logger.warning(warning)
                                self.degradation_status.warnings.append(warning)
                                
                                # Log degradation event
                                retry_logger.log_degradation(warning)
                                
                                # In degraded mode, collect partial results if enabled
                                if COLLECT_PARTIAL_RESULTS and results:
                                    print(f"Collecting partial results: {len(results)} articles retrieved so far")
                                    self.degradation_status.collected_results_count = len(results)
                                    break  # Stop trying more pages for this keyword
                        
                        # Retry logic is handled by @retry_with_backoff decorator
                        break
                    except Exception as e:
                        error_msg = f'Unexpected error for keyword "{keyword}": {str(e)}'
                        print(error_msg)
                        logger.error(error_msg)
                        self.degradation_status.update_failure(error_msg)
                        break

                # Add random delay between keyword searches (anti-bot timing)
                if keyword != keywords[-1] and articles_collected_total < total_articles_target:
                    delay = random.uniform(*RANDOM_DELAY_RANGE)
                    print(f"Waiting {delay:.1f}s before next keyword...")
                    time.sleep(delay)

        except Exception as e:
            print(f"Error in get_news: {str(e)}")
            return pd.DataFrame()

        print(f"\n--- HTML Scraping Finished ---")
        print(f"Collected a total of {len(results)} articles.")
        
        # Report degradation status
        if self.degradation_status.is_degraded:
            print(f"\n⚠️  DEGRADATION WARNING")
            print(f"  - Success Rate: {self.degradation_status.success_rate:.1%}")
            print(f"  - Successful Attempts: {self.degradation_status.successful_attempts}/{self.degradation_status.total_attempts}")
            print(f"  - Failed Attempts: {self.degradation_status.failed_attempts}")
            print(f"  - Consecutive Failures: {self.degradation_status.consecutive_failures}")
            if COLLECT_PARTIAL_RESULTS and results:
                print(f"  - Partial Results Collected: {len(results)} articles")
        
        return pd.DataFrame(results) if results else pd.DataFrame(
            columns=['keywords', 'title', 'url', 'snippet', 'published_time', 'source']
        )
