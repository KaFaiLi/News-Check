"""Module for analyzing news article content."""

import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.models import ArticleAnalysis, TrendAnalysis
from src.config import OPENAI_API_KEY, OPENAI_API_BASE, USE_LLM, LLM_THRESHOLD, OUTPUT_DIR
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from bs4 import BeautifulSoup
import html2text
import time
import os
import json
from pathlib import Path

class ContentAnalyzerSimple:
    def __init__(self):
        """Initialize the content analyzer."""
        print("Initializing ContentAnalyzer with LLM support")
        
        # Use default_headers instead of headers
        custom_headers = {
            "HTTP-Referer": "https://github.com/News-Check",
            "X-Title": "News-Check"
        }

        self.llm = ChatOpenAI(
            model="openai/gpt-4o-mini-2024-07-18",
            temperature=0.7,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            default_headers=custom_headers # Pass headers here
        )
        
        # Initialize HTML to Markdown converter
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = True
        self.h2t.ignore_tables = False
        self.h2t.body_width = 0  # Disable text wrapping
        
        # Paywall detection patterns
        self.paywall_patterns = [
            r'subscribe|sign in|sign up|log in|register|membership|premium|paywall',
            r'to continue reading|to read this article|to view this content',
            r'you have reached your article limit|article limit reached',
            r'this article is for subscribers only|exclusive content',
            r'free trial|start your subscription|become a member'
        ]
        
        # Known paywall domains and their handling methods
        self.paywall_domains = {
            'wsj.com': 'archive',
            'nytimes.com': 'archive',
            'ft.com': 'archive',
            'bloomberg.com': 'archive',
            'economist.com': 'archive',
            'washingtonpost.com': 'archive',
            'businesswire.com': 'alternative',
            'prnewswire.com': 'alternative',
            'reuters.com': 'alternative'
        }
        
        # Create output directory for article content
        self.content_dir = os.path.join(OUTPUT_DIR, 'article_content')
        os.makedirs(self.content_dir, exist_ok=True)
        
        self.keywords = {
            'AI Development': [
                'artificial intelligence research', 'image generation', 'AI impact'
                'AI breakthroughs', 'neural networks', 'large language models'
            ],
            'Fintech': [
                'digital banking', 'blockchain finance', 'payment technology',
                'financial technology', 'cryptocurrency', 'AI Regulation'
            ],
            'GenAI Usage': [
                'generative AI', 'AI applications', 'AI implementation',
                'AI automation', 'AI tools', 'AI agents'
            ]
        }
        # Define the prompt template once
        self.llm_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert news analyst. Analyze the article and provide key insights.
            Focus on:
            1. Main points and key findings
            2. Industry impact and significance
            3. Potential future implications
            4. Any notable quotes or statistics
            Keep the analysis concise but informative."""),
            ("user", """Article Title: {title}
            Content: {description}

            Provide a comprehensive analysis of this article (3-4 sentences).""")
        ])
        self.llm_chain = self.llm_prompt | self.llm

    def _detect_paywall(self, soup: BeautifulSoup, url: str) -> bool:
        """Detect if the page has a paywall or requires subscription."""
        # Check URL domain
        domain = url.split('/')[2]
        if domain in self.paywall_domains:
            return True
            
        # Check for paywall indicators in text
        text = soup.get_text().lower()
        for pattern in self.paywall_patterns:
            if re.search(pattern, text):
                return True
                
        # Check for common paywall elements
        paywall_elements = soup.find_all(['div', 'section'], class_=lambda x: x and any(
            term in x.lower() for term in ['paywall', 'subscription', 'premium', 'membership']
        ))
        if paywall_elements:
            return True
            
        return False

    def _handle_paywalled_content(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """Attempt to handle paywalled content by extracting preview content."""
        try:
            # Look for preview or teaser content
            preview_selectors = [
                '.article-preview',
                '.teaser-content',
                '.article-summary',
                '.preview-content',
                '[class*="preview"]',
                '[class*="teaser"]',
                '.article-excerpt',
                '.summary'
            ]
            
            for selector in preview_selectors:
                preview = soup.select_one(selector)
                if preview:
                    return str(preview)
                    
            # Try to get first few paragraphs
            paragraphs = soup.find_all('p')
            if paragraphs:
                preview_text = '\n\n'.join(p.get_text() for p in paragraphs[:3])
                if len(preview_text) > 100:  # Ensure we have meaningful content
                    return preview_text
                    
        except Exception as e:
            print(f"Preview extraction failed: {str(e)}")
            
        return None

    def fetch_article_content(self, url: str, article_id: str) -> Optional[Dict[str, str]]:
        """Fetch article content from URL using Playwright Edge with new headless mode."""
        max_retries = 3
        retry_delay = 2  # seconds
        last_error = None
        html_content = None # Initialize html_content

        for attempt in range(max_retries):
            print(f"Fetching content from: {url} (Attempt {attempt + 1}/{max_retries}) using Edge")
            try:
                with sync_playwright() as p:
                    # Launch Edge with new headless mode
                    browser = p.chromium.launch(
                        channel="msedge",
                        headless=False, # Disable headless mode
                    )
                    
                    # Create a new context with specific user agent
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
                    )
                    
                    page = context.new_page()
                    
                    # Set extra headers
                    page.set_extra_http_headers({
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Windows"',
                        'Upgrade-Insecure-Requests': '1'
                    })

                    # Navigate to the page
                    response = page.goto(
                        url,
                        timeout=45000,
                        wait_until='domcontentloaded'
                    )

                    # Check response status
                    if not response or not response.ok:
                        status = response.status if response else 'No response'
                        print(f"Error: Received status {status} from {url}")
                        context.close()
                        browser.close()
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            raise PlaywrightError(f"Failed to load page {url} with status {status}")

                    # Wait for content to load
                    try:
                        # Wait for main content to be visible
                        page.wait_for_selector('article, main, .article-content, .post-content, .entry-content', timeout=15000)
                    except PlaywrightTimeoutError:
                        print("Main content selector not found, continuing with full page content")

                    # Wait for network idle
                    try:
                        page.wait_for_load_state('networkidle', timeout=15000)
                    except PlaywrightTimeoutError:
                        print("Network idle timeout, using current state")

                    # Wait an additional 5 seconds to ensure dynamic content is loaded
                    print("Waiting for dynamic content to load...")
                    time.sleep(5)
                    
                    # Get the full page HTML content
                    html_content = page.content()
                    context.close()
                    browser.close()

                # If successful, break the retry loop
                print("HTML fetched successfully via Edge.")
                break 
                
            except PlaywrightTimeoutError:
                print(f"Edge Timeout Error fetching {url}")
                last_error = PlaywrightTimeoutError(f"Timeout fetching {url}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    break
            except PlaywrightError as e:
                print(f"Edge Error: {str(e)}")
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    break
            except Exception as e:
                print(f"Unexpected Error during Edge operation: {str(e)}")
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    break

        # If html_content was not fetched after retries
        if not html_content:
            print(f"Failed to fetch content for {url} after {max_retries} attempts.")
            error_info = {
                'url': url,
                'error_message': str(last_error) if last_error else 'Failed to fetch content after retries',
                'timestamp': datetime.now().isoformat(),
                'fetch_method': 'edge'
            }
            self._save_error_info(article_id, error_info)
            return None

        # Convert HTML to markdown first
        try:
            print("Converting HTML to markdown...")
            # Configure html2text for better markdown conversion
            self.h2t.ignore_links = False
            self.h2t.ignore_images = True
            self.h2t.ignore_tables = False
            self.h2t.body_width = 0
            self.h2t.unicode_snob = True
            self.h2t.escape_all = True
            
            # Convert HTML to markdown
            raw_markdown = self.h2t.handle(html_content)
            
            # Use LLM to extract the article content from markdown
            print("Using LLM to extract article content...")
            llm_prompt = f"""Please extract the main article content from the following markdown text. 
            Focus on the actual article content and remove any navigation, ads, or other non-article elements.
            Return only the extracted content in markdown format:

            {raw_markdown[:4000]}  # Limit to first 4000 chars to avoid token limits
            """
            
            try:
                llm_response = self.llm.invoke(llm_prompt)
                extracted_content = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
                print(f"Extracted content length: {len(extracted_content)}")
                
                if not extracted_content or len(extracted_content.strip()) < 100:
                    print("LLM extraction failed or returned insufficient content")
                    return None
                    
                # Save both raw and extracted content
                content_dict = {
                    'html': html_content,
                    'raw_markdown': raw_markdown,
                    'extracted_markdown': extracted_content,
                    'url': url
                }
                self._save_article_content(article_id, content_dict)
                    
                return content_dict
                
            except Exception as e:
                print(f"Error processing content: {str(e)}")
                error_info = {
                    'url': url,
                    'error_message': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'fetch_method': 'edge'
                }
                self._save_error_info(article_id, error_info)
                return None
            
        except Exception as e:
            print(f"Error processing content: {str(e)}")
            error_info = {
                'url': url,
                'error_message': str(e),
                'timestamp': datetime.now().isoformat(),
                'fetch_method': 'edge'
            }
            self._save_error_info(article_id, error_info)
            return None

    def _save_error_info(self, article_id: str, error_info: Dict):
        """Saves error information to a JSON file."""
        try:
            error_dir = os.path.join(self.content_dir, 'errors')
            os.makedirs(error_dir, exist_ok=True)
            # Use a more specific error filename if article_id is available
            filename = f'error_{article_id}.json' if article_id else f'error_{int(time.time())}.json'
            error_file = os.path.join(error_dir, filename)
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2)
            print(f"Saved error details to: {error_file}")
        except Exception as e:
            print(f"Critical: Error saving error information: {str(e)}")

    def _save_article_content(self, article_id: str, content: Dict[str, str]):
        """Save article content to files."""
        try:
            # Create article-specific directory
            article_dir = os.path.join(self.content_dir, article_id)
            os.makedirs(article_dir, exist_ok=True)
            
            # Save HTML content
            with open(os.path.join(article_dir, 'content.html'), 'w', encoding='utf-8') as f:
                f.write(content['html'])
            
            # Save markdown content
            with open(os.path.join(article_dir, 'content.md'), 'w', encoding='utf-8') as f:
                f.write(content['extracted_markdown'])
            
            # Save metadata
            metadata = {
                'url': content['url'],
                'fetch_time': datetime.now().isoformat(),
                'content_length': len(content['extracted_markdown'])
            }
            with open(os.path.join(article_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            print(f"Error saving article content: {str(e)}")

    def analyze_article(self, article):
        """Analyze a single article for relevance based on keywords and trending factors."""
        scores = {}
        article_title = article.get('title', '').lower()
        article_desc = article.get('snippet', '').lower()

        for category, keywords in self.keywords.items():
            category_score = 0
            for keyword in keywords:
                title_score = fuzz.partial_ratio(keyword.lower(), article_title)
                desc_score = fuzz.partial_ratio(keyword.lower(), article_desc)
                category_score = max(category_score, (title_score + desc_score) / 2)
            scores[category] = category_score / 100.0

        # Calculate overall score as weighted average of keyword relevance and trending score
        keyword_score = max(scores.values()) if scores else 0.0
        trending_score = self.calculate_trending_score(article, [article])  # Pass single article for initial scoring
        
        # Weight the scores (60% keywords, 40% trending)
        overall_score = (0.6 * keyword_score) + (0.4 * trending_score)

        return {
            'scores': scores,
            'insights': None,  # Initialize insights as None
            'trending_score': trending_score,
            'keyword_score': keyword_score,
            'overall_score': overall_score
        }

    def get_llm_insights(self, article_data: Dict) -> Optional[str]:
        """Get LLM-generated insights for a single article's content."""
        try:
            if not USE_LLM:
                return None

            # Fetch article content if URL is available
            article_content = None
            if 'url' in article_data:
                article_content = self.fetch_article_content(article_data['url'], '')
                if article_content:
                    print("Successfully fetched article content")
                else:
                    print("Could not fetch article content, using snippet only")

            # Prepare the prompt with available content
            content = article_content['extracted_markdown'] if article_content else article_data.get('snippet', 'No Description')
            
            insights_result = self.llm_chain.invoke({
                "title": article_data.get('title', 'No Title'),
                "description": content
            })
            
            # Handle different response types
            if hasattr(insights_result, 'content'):
                return str(insights_result.content)
            else:
                return str(insights_result)
                
        except Exception as e:
            print(f"Error getting LLM insights for article '{article_data.get('title', 'Unknown')}': {e}")
            return None

    def rank_articles(self, articles, top_n=20):
        """Rank articles based on relevance scores and trending factors."""
        print(f"\n--- Starting Article Analysis ---")
        print(f"Analyzing {len(articles)} unique articles for initial scoring...")
        analyzed_articles = []
        for i, article in enumerate(articles):
            if (i + 1) % 50 == 0:
                print(f"  Scored {i+1}/{len(articles)} articles...")
            analysis = self.analyze_article(article)
            analyzed_articles.append({
                'article': article,
                'analysis': analysis
            })
        print("Initial scoring complete.")

        # Update trending scores with full article context
        print("Updating trending scores with full article context...")
        for item in analyzed_articles:
            article = item['article']
            trending_score = self.calculate_trending_score(article, articles)
            # Update overall score with new trending score (60% keywords, 40% trending)
            item['analysis']['trending_score'] = trending_score
            item['analysis']['overall_score'] = (0.6 * item['analysis']['keyword_score']) + (0.4 * trending_score)

        # Sort by overall score
        sorted_articles = sorted(analyzed_articles, key=lambda x: x['analysis']['overall_score'], reverse=True)
        
        # Initialize result list and tracking variables
        successful_articles = []
        failed_indices = []
        current_index = 0
        
        print(f"\n--- Fetching Content for Top Articles ---")
        print(f"Target: {top_n} articles with content")
        
        # Continue processing until we have top_n successful articles or run out of candidates
        while len(successful_articles) < top_n and current_index < len(sorted_articles):
            item = sorted_articles[current_index]
            article = item.get('article')
            analysis = item.get('analysis')
            
            # Basic validation
            if not article or not analysis:
                print(f"Warning: Skipping invalid article at index {current_index}")
                failed_indices.append(current_index)
                current_index += 1
                continue
                
            print(f"\nProcessing article {len(successful_articles) + 1}/{top_n}")
            print(f"Article: {article.get('title', 'Unknown Title')[:80]}...")
            print(f"Score: {analysis.get('overall_score', 0):.2f}")
            
            # Generate article ID
            safe_title = re.sub(r'[^\w\-]+', '_', article.get('title', 'untitled')[:30])
            article_id = f"{len(successful_articles) + 1:02d}_{safe_title}_{int(time.time())}"
            
            # Attempt to fetch content
            article_url = article.get('url')
            if not article_url:
                print("No URL found - skipping article")
                failed_indices.append(current_index)
                current_index += 1
                continue
                
            print(f"Fetching content from: {article_url}")
            content_result = self.fetch_article_content(article_url, article_id)
            
            if content_result and 'extracted_markdown' in content_result and len(content_result['extracted_markdown'].strip()) > 100:
                # Content fetch successful
                print("Content fetched successfully")
                item['article']['fetched_content'] = content_result
                
                # Get LLM insights if enabled and content is substantial
                if USE_LLM and analysis.get('overall_score', 0) >= LLM_THRESHOLD:
                    print(f"Getting LLM insights...")
                    insights = self.get_llm_insights({
                        'title': article.get('title', ''),
                        'description': content_result['extracted_markdown']
                    })
                    item['analysis']['insights'] = insights
                    if insights:
                        print("LLM insights generated successfully")
                    else:
                        print("LLM insights generation failed")
                else:
                    print("Skipping LLM insights (disabled or low score)")
                    item['analysis']['insights'] = None
                
                successful_articles.append(item)
                print(f"Article {len(successful_articles)}/{top_n} processed successfully")
            else:
                print("Failed to fetch meaningful content - skipping article")
                failed_indices.append(current_index)
            
            current_index += 1
            
        # Summary
        print("\n--- Content Fetching Summary ---")
        print(f"Processed {current_index} articles total")
        print(f"Successfully fetched content for {len(successful_articles)}/{top_n} articles")
        print(f"Skipped {len(failed_indices)} articles due to fetch failures or invalid data")
        
        if len(successful_articles) < top_n:
            print(f"\nWarning: Only found {len(successful_articles)} articles with valid content")
            print("Consider adjusting search criteria or increasing the source article pool")
            
        return successful_articles

    def remove_duplicates(self, articles, threshold=75):
        """Remove duplicate articles based on title similarity."""
        unique_articles = []
        seen_titles = set() # Use a set for faster lookups
        for article in articles:
            title = article.get('title', '')
            is_duplicate = False
            # Check against already added unique titles first for efficiency
            if title in seen_titles:
                 # Quick check for exact match
                 is_duplicate = True
            else:
                 # Check similarity against previous unique articles if not an exact match
                 for unique in unique_articles:
                     similarity = fuzz.ratio(title, unique.get('title', ''))
                     if similarity > threshold:
                         is_duplicate = True
                         break # Found a duplicate

            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(title) # Add title to set
        return unique_articles

    def calculate_trending_score(self, article: Dict, all_articles: List[Dict]) -> float:
        """Calculate trending score based on frequency, time, and source reliability"""
        # Calculate frequency score (how many similar articles exist)
        frequency_score = 0
        article_title_lower = article.get('title', '').lower()
        for other_article in all_articles:
            if other_article != article:
                similarity = fuzz.ratio(article_title_lower, other_article.get('title', '').lower())
                if similarity > 60:  # Lower threshold for counting related articles
                    frequency_score += 1
        frequency_score = min(frequency_score / 10, 1.0)  # Normalize to 0-1

        # Calculate time score (how recent the article is)
        time_score = 0.5  # Default score for unknown times
        try:
            article_time_str = article.get('published_time', '')
            if article_time_str and article_time_str != 'Unknown Time':
                # Try different date formats
                try:
                    # Try ISO format first
                    article_time = datetime.fromisoformat(article_time_str.replace('Z', '+00:00'))
                except ValueError:
                    # If ISO format fails, try to parse relative time
                    current_time = datetime.now(datetime.timezone.utc)
                    if 'hour' in article_time_str.lower():
                        hours = int(''.join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(hours=hours)
                    elif 'day' in article_time_str.lower():
                        days = int(''.join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(days=days)
                    elif 'minute' in article_time_str.lower():
                        minutes = int(''.join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(minutes=minutes)
                    elif 'week' in article_time_str.lower():
                        weeks = int(''.join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(weeks=weeks)
                    else:
                        raise ValueError(f"Unrecognized time format: {article_time_str}")

                # Make datetime aware if it's naive
                if article_time.tzinfo is None:
                    article_time = article_time.replace(tzinfo=datetime.timezone.utc)

                # Calculate time score
                now_aware = datetime.now(datetime.timezone.utc)
                time_diff = now_aware - article_time
                time_score = max(1 - (time_diff.total_seconds() / (7 * 24 * 3600)), 0)  # 7 days window

        except Exception as e:
            print(f"Notice: Using default time score for '{article_time_str}'. Reason: {str(e)}")
            # Keep using default time_score of 0.5

        # Calculate source reliability score
        trusted_sources = ['Reuters', 'Bloomberg', 'Financial Times', 'Wall Street Journal',
                          'TechCrunch', 'Wired', 'MIT Technology Review', 'Harvard Business Review']
        source = article.get('source', '').lower()
        source_score = 0.8  # Default score
        for trusted in trusted_sources:
            if trusted.lower() in source:
                source_score = 1.0
                break

        # Combine scores with weights
        trending_score = (0.2 * time_score) + (0.3 * frequency_score) + (0.5 * source_score)
        return trending_score

    def generate_topic_summary(self, top_articles: List[Dict]) -> Dict:
        """Generate a summary of top AI and fintech news by topic"""
        # Group articles by their highest scoring category
        articles_by_category = {'AI Development': [], 'Fintech': [], 'GenAI Usage': [], 'Other': []}

        for item in top_articles:
            scores = item['analysis']['scores']
            if not scores: # Handle case where scores might be empty
                 articles_by_category['Other'].append(item)
                 continue

            # Find the category with the highest score
            top_category = max(scores, key=scores.get)

            # Assign to category if score is meaningful, otherwise 'Other'
            # You might want a threshold here, e.g., max score > 0.2
            if scores[top_category] > 0.1: # Example threshold
                 if top_category in articles_by_category:
                     articles_by_category[top_category].append(item)
                 else:
                     articles_by_category['Other'].append(item) # Should not happen with current keywords
            else:
                articles_by_category['Other'].append(item)

        return {
            'top_articles': top_articles, # Pass the original list containing analysis etc.
            'ai_development_count': len(articles_by_category['AI Development']),
            'fintech_count': len(articles_by_category['Fintech']),
            'genai_usage_count': len(articles_by_category['GenAI Usage']),
            'other_count': len(articles_by_category['Other']),
            'top_impact': self._get_high_impact_articles(top_articles) # Use overall_score now
        }

    def _get_high_impact_articles(self, articles: List[Dict]) -> List[Dict]:
        """Extract top 3 articles based on overall_score"""
        # Sort by 'overall_score' found within the 'analysis' dictionary
        articles.sort(key=lambda x: x.get('analysis', {}).get('overall_score', 0), reverse=True)
        # Return the top 3 items (which contain both 'article' and 'analysis')
        return articles[:3] 