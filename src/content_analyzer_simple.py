"""Module for analyzing news article content."""

import re
from typing import List, Dict, Optional
from datetime import datetime
from fuzzywuzzy import fuzz
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.models import ArticleAnalysis, TrendAnalysis
from src.config import OPENAI_API_KEY, OPENAI_API_BASE, USE_LLM, LLM_THRESHOLD, OUTPUT_DIR
import requests
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
        
        # Add request headers for fetching article content
        self.request_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
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
        """Attempt to handle paywalled content using various strategies."""
        domain = url.split('/')[2]
        strategy = self.paywall_domains.get(domain, 'alternative')
        
        if strategy == 'archive':
            # Try to get archived version
            try:
                archive_url = f"https://web.archive.org/web/*/{url}"
                response = requests.get(archive_url, headers=self.request_headers, timeout=30)
                if response.status_code == 200:
                    archive_soup = BeautifulSoup(response.text, 'html.parser')
                    # Try to find the most recent snapshot
                    snapshots = archive_soup.find_all('div', class_='captures')
                    if snapshots:
                        latest_snapshot = snapshots[0].find('a')
                        if latest_snapshot:
                            archive_url = latest_snapshot['href']
                            response = requests.get(archive_url, headers=self.request_headers, timeout=30)
                            if response.status_code == 200:
                                return response.text
            except Exception as e:
                print(f"Archive strategy failed: {str(e)}")
        
        # Try to extract preview content
        try:
            # Look for preview or teaser content
            preview_selectors = [
                '.article-preview',
                '.teaser-content',
                '.article-summary',
                '.preview-content',
                '[class*="preview"]',
                '[class*="teaser"]'
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
        """Fetch article content from URL and convert to markdown with improved error handling."""
        max_retries = 3
        retry_delay = 2  # seconds
        last_error = None
        
        for attempt in range(max_retries):
            try:
                print(f"Fetching content from: {url} (Attempt {attempt + 1}/{max_retries})")
                
                # Add timeout and verify SSL
                response = requests.get(
                    url, 
                    headers=self.request_headers, 
                    timeout=30,
                    verify=True  # Enable SSL verification
                )
                
                # Check for specific HTTP status codes
                if response.status_code == 403:
                    print("Access forbidden (403). Trying with different headers...")
                    # Try with alternative headers
                    alt_headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://www.google.com/'
                    }
                    response = requests.get(url, headers=alt_headers, timeout=30, verify=True)
                
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for paywall
                if self._detect_paywall(soup, url):
                    print("Paywall detected. Attempting to handle...")
                    paywall_content = self._handle_paywalled_content(url, soup)
                    if paywall_content:
                        print("Successfully extracted content from paywalled article")
                        soup = BeautifulSoup(paywall_content, 'html.parser')
                    else:
                        print("Could not extract content from paywalled article")
                        return None
                
                # Remove unwanted elements
                for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'iframe']):
                    element.decompose()
                
                # Try to find the main content
                main_content = None
                content_selectors = [
                    'article',  # Common article tag
                    'main',     # Main content
                    '.article-content',  # Common class
                    '.post-content',
                    '#content',
                    '.content'
                ]
                
                for selector in content_selectors:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                # If no specific content found, use the whole body
                if not main_content:
                    main_content = soup.find('body')
                    if not main_content:
                        main_content = soup
                
                # Get cleaned HTML
                cleaned_html = str(main_content)
                
                # Convert to markdown
                markdown_content = self.h2t.handle(cleaned_html)
                
                # Clean up the markdown
                markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)  # Remove excessive newlines
                markdown_content = re.sub(r'\[.*?\]\(.*?\)', '', markdown_content)  # Remove markdown links
                markdown_content = re.sub(r'#+\s*', '', markdown_content)  # Remove headers
                markdown_content = markdown_content.strip()
                
                # Check if we got meaningful content
                if len(markdown_content) < 100:  # If content is too short
                    print("Warning: Retrieved content seems too short. Trying alternative content extraction...")
                    # Try to get text from all paragraphs
                    paragraphs = soup.find_all('p')
                    if paragraphs:
                        markdown_content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs)
                
                # Save both HTML and markdown content
                content = {
                    'html': cleaned_html,
                    'markdown': markdown_content[:5000],  # Limit markdown content length
                    'url': url,
                    'fetch_attempts': attempt + 1,
                    'is_paywalled': self._detect_paywall(soup, url)
                }
                
                # Save to files
                self._save_article_content(article_id, content)
                
                return content
                
            except requests.exceptions.SSLError as e:
                print(f"SSL Error: {str(e)}")
                last_error = e
                if attempt < max_retries - 1:
                    print(f"Retrying with SSL verification disabled...")
                    try:
                        response = requests.get(url, headers=self.request_headers, timeout=30, verify=False)
                        response.raise_for_status()
                        # Continue with content processing...
                    except Exception as e:
                        last_error = e
                        time.sleep(retry_delay)
                        continue
                
            except requests.exceptions.RequestException as e:
                print(f"Request Error: {str(e)}")
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                
            except Exception as e:
                print(f"Unexpected Error: {str(e)}")
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
        
        # If all retries failed, save error information
        error_info = {
            'url': url,
            'error_type': type(last_error).__name__ if last_error else 'Unknown',
            'error_message': str(last_error) if last_error else 'Unknown error',
            'timestamp': datetime.now().isoformat(),
            'is_paywalled': self._detect_paywall(BeautifulSoup('', 'html.parser'), url) if last_error else False
        }
        
        # Save error information
        try:
            error_dir = os.path.join(self.content_dir, 'errors')
            os.makedirs(error_dir, exist_ok=True)
            error_file = os.path.join(error_dir, f'error_{article_id}.json')
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2)
        except Exception as e:
            print(f"Error saving error information: {str(e)}")
        
        return None

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
                f.write(content['markdown'])
            
            # Save metadata
            metadata = {
                'url': content['url'],
                'fetch_time': datetime.now().isoformat(),
                'content_length': len(content['markdown'])
            }
            with open(os.path.join(article_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            print(f"Error saving article content: {str(e)}")

    def analyze_article(self, article):
        """Analyze a single article for relevance based on keywords (no LLM call here)."""
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

        # Return only scores, insights will be added later for top articles
        return {
            'scores': scores,
            'insights': None, # Initialize insights as None
            'overall_score': max(scores.values()) if scores else 0.0 # Handle empty scores case
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
            content = article_content if article_content else article_data.get('snippet', 'No Description')
            
            insights_result = self.llm_chain.invoke({
                "title": article_data.get('title', 'No Title'),
                "description": content
            })
            return str(insights_result.content)
        except Exception as e:
            print(f"Error getting LLM insights for article '{article_data.get('title', 'Unknown')}': {e}")
            return None

    def rank_articles(self, articles, top_n=20):
        """Rank articles based on relevance scores, get LLM insights for top N, return top N."""
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
        print("Scoring complete.")

        # Sort by overall score
        sorted_articles = sorted(analyzed_articles, key=lambda x: x['analysis']['overall_score'], reverse=True)

        # Select top N articles
        top_articles_to_analyze = sorted_articles[:top_n]
        print(f"\nSelected top {len(top_articles_to_analyze)} articles for content fetching and analysis.")

        # Fetch content and get LLM insights for the top N articles
        for i, item in enumerate(top_articles_to_analyze):
            print(f"\nProcessing article {i+1}/{len(top_articles_to_analyze)}...")
            article_content = None
            article = item['article']
            
            # Generate a unique ID for the article
            article_id = f"article_{i+1:02d}_{int(time.time())}"
            
            # Fetch content if URL is available
            if 'url' in article:
                content_result = self.fetch_article_content(article['url'], article_id)
                if content_result:
                    article_content = content_result['markdown']
                    item['article']['content'] = content_result
                    print("Successfully fetched and saved article content")
                else:
                    print("Could not fetch article content")
            
            # Get LLM insights if enabled
            if USE_LLM and item['analysis']['overall_score'] >= LLM_THRESHOLD:
                content_for_analysis = article_content if article_content else article.get('snippet', '')
                insights = self.get_llm_insights({'title': article.get('title', ''), 'description': content_for_analysis})
                item['analysis']['insights'] = insights
            else:
                item['analysis']['insights'] = None

        print("\nContent fetching and analysis complete.")
        return top_articles_to_analyze

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
        try:
            # Use current timezone if not specified in the ISO string
            article_time_str = article.get('published_time')
            if article_time_str:
                article_time = datetime.fromisoformat(article_time_str.replace('Z', '+00:00'))
                # Make datetime aware if it's naive, assuming UTC if parsed as naive
                if article_time.tzinfo is None:
                     article_time = article_time.replace(tzinfo=datetime.timezone.utc)

                # Make now() timezone-aware (using UTC for comparison)
                now_aware = datetime.now(datetime.timezone.utc)
                time_diff = now_aware - article_time
                time_score = max(1 - (time_diff.total_seconds() / (7 * 24 * 3600)), 0)  # 7 days window
            else:
                 time_score = 0.5 # Default score if no time provided

        except Exception as e:
            print(f"Warning: Could not parse date '{article.get('published_time')}', using default time score. Error: {e}")
            time_score = 0.5  # Default score if date parsing fails

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