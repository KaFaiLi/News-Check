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
from src.config import MAX_RETRIES, INITIAL_DELAY, MAX_ARTICLES, REQUEST_TIMEOUT, USER_AGENT, OUTPUT_DIR

# Rename class to reflect scraping method
class GoogleNewsScraper:
    def __init__(self, max_articles_per_keyword=MAX_ARTICLES, location='US', language='en'):
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
        total_articles_target = max_articles if max_articles is not None else float('inf') # Overall limit if provided
        articles_collected_total = 0
        
        # Update max articles per keyword if overall limit is lower than default per keyword
        current_max_per_keyword = self.max_articles_per_keyword
        if max_articles is not None:
             # Rough distribution - aim for slightly more per keyword initially if overall limit is set
             current_max_per_keyword = max(self.max_articles_per_keyword, (max_articles // len(keywords)) + 5)
        
        try:
            for keyword in keywords:
                if articles_collected_total >= total_articles_target:
                     print("Reached overall article limit. Stopping search.")
                     break

                print(f'\nSearching for keyword: "{keyword}"')
                articles_found_for_keyword = 0

                # Construct search parameters
                params = {
                    'q': keyword,
                    'tbm': 'nws',  # Specify News search
                    'hl': self.language,
                    'gl': self.location,
                }

                html_content = None
                delay = self.initial_delay

                # Fetching loop
                for retry in range(self.max_retries):
                    try:
                        print(f'Fetching page for keyword: "{keyword}" (Attempt {retry + 1}/{self.max_retries})')
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

                        html_content = response.text
                        print("HTML fetched successfully.")
                        break

                    except requests.exceptions.RequestException as e:
                        print(f'Request failed: {str(e)}')
                        if retry == self.max_retries - 1:
                            print(f'Failed to fetch page after {self.max_retries} attempts.')
                            continue  # Skip to next keyword
                        delay *= 2
                        print(f'Retrying in {delay} seconds...')
                        time.sleep(delay)
                    except Exception as e:
                        print(f'Unexpected error: {str(e)}')
                        if retry == self.max_retries - 1:
                            print(f'Failed after {self.max_retries} attempts.')
                            continue  # Skip to next keyword
                        delay *= 2
                        print(f'Retrying in {delay} seconds...')
                        time.sleep(delay)

                if not html_content:
                    continue

                # Parse HTML
                try:
                    print("Parsing HTML content...")
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # Updated selectors based on our testing
                    articles = soup.select('div.SoaBEf')  # Main article container
                    print(f"Found {len(articles)} articles on page.")

                    for article in articles:
                        if articles_collected_total >= total_articles_target:
                            break
                        if articles_found_for_keyword >= current_max_per_keyword:
                            break

                        try:
                            # Extract title (using all classes)
                            title_element = article.select_one('div.n0jPhd.ynAwRc.MBeuO.nDgy9d')
                            if not title_element:
                                continue
                            title = title_element.get_text(strip=True)

                            # Extract source (using both classes)
                            source_element = article.select_one('div.MgUUmf.NUnG9d')
                            source = source_element.get_text(strip=True) if source_element else "Unknown Source"

                            # Extract snippet
                            snippet_element = article.select_one('div.GI74Re.nDgy9d')
                            snippet = snippet_element.get_text(strip=True) if snippet_element else ""

                            # Extract link
                            link_element = article.select_one('a[href]')  # Find first link
                            link = link_element['href'] if link_element else "#"
                            # Handle Google's redirect URLs
                            if link.startswith('/url?'):
                                link = f"https://www.google.com{link}"

                            # Extract time (last span without class)
                            spans = article.find_all('span', class_='')
                            pub_time_str = spans[-1].get_text(strip=True) if spans else "Unknown Time"
                            # Try to parse the time
                            pub_time_obj = self._parse_relative_time(pub_time_str)
                            pub_time = pub_time_obj.isoformat() if pub_time_obj else pub_time_str

                            # Store the article data
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
                            print(f"Found article {articles_found_for_keyword}: {title[:60]}...")

                        except Exception as e:
                            print(f"Error processing article: {str(e)}")
                            continue

                    print(f'Found {articles_found_for_keyword} articles for keyword "{keyword}"')

                except Exception as e:
                    print(f"Error parsing HTML for keyword '{keyword}': {e}")
                    continue

                # Add delay between keywords
                if keyword != keywords[-1]:
                    time.sleep(self.initial_delay)

        except Exception as e:
            print(f"Error in get_news: {str(e)}")
            return pd.DataFrame()  # Return empty DataFrame on any error

        print(f"\n--- HTML Scraping Finished ---")
        print(f"Collected a total of {len(results)} articles.")

        # Create DataFrame
        df = pd.DataFrame(results) if results else pd.DataFrame(
            columns=['keywords', 'title', 'url', 'snippet', 'published_time', 'source']
        )
        return df
    
    # _clean_html is likely not needed anymore as we use .get_text(strip=True) from BeautifulSoup
    # def _clean_html(self, text): ...


# --- Main function remains largely the same, but uses GoogleNewsScraper ---
def main():
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Initialize the updated scraper class
        scraper_instance = GoogleNewsScraper(
            max_articles_per_keyword=25, # Limit per keyword
            location='US',
            language='en'
        )

        keywords = [
            'artificial intelligence research', 'machine learning breakthrough', 'neural network development',
            'fintech innovation', 'digital banking technology', 'blockchain finance',
            'generative AI', 'ChatGPT enterprise', 'AI content creation'
        ]
        end_date = datetime.now().strftime('%Y-%m-%d')
        # Go back 7 days for example
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        print(f"\nFetching news via HTML scraping (google.com/search) from {start_date} to {end_date}")
        
        # Get news using the scraper, setting an overall limit
        # Set a reasonable overall limit, e.g., 100
        df = scraper_instance.get_news(keywords, start_date, end_date, max_articles=100)
        
        if df.empty:
            print("No articles were found via HTML scraping. Check selectors, network, date range, or try RSS.")
            return
        
        # --- Save raw scraped data to Excel ---
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"scraped_news_raw_{timestamp}.xlsx"
            excel_filepath = os.path.join(OUTPUT_DIR, excel_filename)
            print(f"\nSaving raw scraped data to Excel: {excel_filepath}")
            df.to_excel(excel_filepath, index=False, engine='openpyxl')
            print(f"Successfully saved raw data to {excel_filepath}")
        except Exception as e:
            print(f"Warning: Could not save raw data to Excel. Error: {e}")
        # --- End Excel Saving ---

        print("\nInitializing content analyzer...")
        analyzer = ContentAnalyzerSimple() # Analyzer logic remains the same
        
        articles = df.to_dict('records')
        
        print("\nRemoving duplicate articles...")
        unique_articles = analyzer.remove_duplicates(articles) # Duplicate removal remains the same
        print(f'Found {len(unique_articles)} unique articles after removing duplicates')
        
        if not unique_articles:
             print("No unique articles left after duplicate removal.")
             return

        print("\nRanking and analyzing articles...")
        # Limit LLM analysis to top N (e.g., 20) as configured before
        top_articles = analyzer.rank_articles(unique_articles, top_n=20)

        if not top_articles:
             print("\nNo articles ranked high enough to generate reports.")
             return

        topic_summary = analyzer.generate_topic_summary(top_articles)
        
        print("\nInitializing document generator...")
        # Pass LLM instance to generator as before
        doc_generator = DocumentGenerator(llm_instance=analyzer.llm)
        
        print("\nGenerating Word documents...")
        brief_doc_path = doc_generator.generate_brief_summary(top_articles)
        print(f"Generated brief summary document: {brief_doc_path}")
        detailed_doc_path = doc_generator.generate_detailed_report(top_articles)
        print(f"Generated detailed report: {detailed_doc_path}")
        
        # Display category breakdown
        print(f'\nCategory Breakdown for Top {len(top_articles)} Articles:')
        print(f'  AI Development: {topic_summary["ai_development_count"]} articles')
        print(f'  Fintech: {topic_summary["fintech_count"]} articles')
        print(f'  GenAI Usage: {topic_summary["genai_usage_count"]} articles')
        print(f'  Other: {topic_summary["other_count"]} articles')
        
        print("\nDocuments have been generated successfully!")
        
    except Exception as e:
        print(f"An error occurred in main: {str(e)}")
        import traceback
        print("Traceback:")
        print(traceback.format_exc()) # Print full traceback for easier debugging
        # raise # Optionally re-raise

if __name__ == "__main__":
    # Ensure dependencies are checked/installed
    try:
        import bs4
    except ImportError:
        print("Note: 'beautifulsoup4' library not found. Please install it ('pip install beautifulsoup4').")
        # Consider adding auto-install or exiting
    try:
        import openpyxl
    except ImportError:
        print("Note: 'openpyxl' library not found. Attempting install...")
        import subprocess, sys
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            print("'openpyxl' installed successfully.")
        except Exception as install_error:
            print(f"Failed to install 'openpyxl'. Please install manually. Error: {install_error}")

    main() 