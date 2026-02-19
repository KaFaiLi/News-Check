"""Module for analyzing news article content."""

import re
import random  # For random delays
import logging  # For comprehensive logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from fuzzywuzzy import fuzz
from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr
import importlib
from langchain_core.prompts import ChatPromptTemplate
from src.models import ArticleAnalysis, TrendAnalysis
from src.config import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    AZURE_DEPLOYMENT_NAME,
    AZURE_API_VERSION,
    USE_LLM,
    LLM_THRESHOLD,
    OUTPUT_DIR,
    RANDOM_DELAY_RANGE,
)
from src.config import (
    ENABLE_GRACEFUL_DEGRADATION,
    MAX_CONSECUTIVE_FAILURES,
    COLLECT_PARTIAL_RESULTS,
)
from src.config import (
    SOURCE_RELIABILITY_TIER_1,
    SOURCE_RELIABILITY_TIER_2,
    TIER_1_MULTIPLIER,
    TIER_2_MULTIPLIER,
    TIER_3_MULTIPLIER,
)
from src.config import (
    SCORE_WEIGHT_KEYWORD,
    SCORE_WEIGHT_TRENDING,
    SCORE_WEIGHT_SOURCE,
    MAX_ARTICLES_PER_SOURCE,
)
from src.config import MAX_MARKDOWN_LENGTH, TRUNCATION_INDICATOR, REQUEST_TIMEOUT
from src.config import (
    RELEVANCE_KEYWORD_DENSITY_WEIGHT,
    RELEVANCE_RECENCY_WEIGHT,
    RELEVANCE_SOURCE_WEIGHT,
    RELEVANCE_DUPLICATE_PENALTY_WEIGHT,
    MIN_EXTRACTED_TEXT_LENGTH,
    MIN_EXTRACTED_PARAGRAPHS,
)
from src.retry_policy import retry_with_backoff
from src.user_agent_pool import user_agent_pool
from src.retry_logger import retry_logger
from src.models import DegradationStatus, BlockType
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from bs4 import BeautifulSoup
import html2text

trafilatura = None
Document = None
import time
import os
import json
import sys
from pathlib import Path
from src.block_detector import BlockDetector
from src.url_utils import normalize_url

# NOTE: LSP may flag missing optional dependencies locally.

# Module-level logger
logger = logging.getLogger(__name__)


class ContentAnalyzerSimple:
    def __init__(self):
        """Initialize the content analyzer."""
        print("Initializing ContentAnalyzer with LLM support")

        # Degradation tracking (Phase 5)
        self.degradation_status = DegradationStatus()

        # Use default_headers instead of headers
        self.llm = AzureChatOpenAI(
            azure_deployment=AZURE_DEPLOYMENT_NAME,
            api_version=AZURE_API_VERSION,
            temperature=0.7,
            api_key=SecretStr(OPENAI_API_KEY),
            azure_endpoint=OPENAI_API_BASE,
        )

        # Initialize HTML to Markdown converter
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = True
        self.h2t.ignore_tables = False
        self.h2t.body_width = 0  # Disable text wrapping

        # Paywall detection patterns
        self.paywall_patterns = [
            r"subscribe|sign in|sign up|log in|register|membership|premium|paywall",
            r"to continue reading|to read this article|to view this content",
            r"you have reached your article limit|article limit reached",
            r"this article is for subscribers only|exclusive content",
            r"free trial|start your subscription|become a member",
        ]

        # Known paywall domains and their handling methods
        self.paywall_domains = {
            "wsj.com": "archive",
            "nytimes.com": "archive",
            "ft.com": "archive",
            "bloomberg.com": "archive",
            "economist.com": "archive",
            "washingtonpost.com": "archive",
            "businesswire.com": "alternative",
            "prnewswire.com": "alternative",
            "reuters.com": "alternative",
        }

        # Create output directory for article content
        self.content_dir = os.path.join(OUTPUT_DIR, "article_content")
        os.makedirs(self.content_dir, exist_ok=True)

        self.keywords = {
            "AI Development": [
                "artificial intelligence research",
                "image generation",
                "AI impactAI breakthroughs",
                "neural networks",
                "large language models",
            ],
            "Fintech": [
                "digital banking",
                "blockchain finance",
                "payment technology",
                "financial technology",
                "cryptocurrency",
                "AI Regulation",
            ],
            "GenAI Usage": [
                "generative AI",
                "AI applications",
                "AI implementation",
                "AI automation",
                "AI tools",
                "AI agents",
            ],
        }
        # Define the prompt template once
        self.llm_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert news analyst. Analyze the article and provide exactly three key insights as bullet points.
            Focus on:
            1. Main findings or announcements
            2. Industry impact and significance
            3. Future implications or next steps
            
            Format your response as three bullet points, each starting with '•'. Keep each bullet point concise but informative.""",
                ),
                (
                    "user",
                    """Article Title: {title}
            Content: {description}

            Provide exactly three key insights as bullet points:""",
                ),
            ]
        )
        self.llm_chain = self.llm_prompt | self.llm

    def get_base_domain(self, url: str) -> str:
        """Extract base domain from URL for source tier matching.

        Examples:
            'https://www.cnn.com/article' -> 'cnn.com'
            'https://news.bbc.co.uk/story' -> 'bbc.co.uk'

        Args:
            url: Full article URL

        Returns:
            Base domain string (without www prefix)
        """
        from urllib.parse import urlparse

        try:
            netloc = urlparse(url).netloc.lower()
            # Remove www. prefix for matching
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception as e:
            logger.warning(f"Error extracting domain from {url}: {e}")
            return ""

    def get_source_tier(self, url: str) -> int:
        """Determine source reliability tier from article URL.

        Args:
            url: Full article URL

        Returns:
            1 for tier-1 (premium sources)
            2 for tier-2 (established sources)
            3 for tier-3 (unranked/unknown sources)
        """
        from src.config import SOURCE_RELIABILITY_TIER_1, SOURCE_RELIABILITY_TIER_2

        base_domain = self.get_base_domain(url)
        if not base_domain:
            return 3

        # Check tier-1 (subdomain-flexible matching)
        for domain in SOURCE_RELIABILITY_TIER_1:
            if base_domain == domain or base_domain.endswith("." + domain):
                return 1

        # Check tier-2 (subdomain-flexible matching)
        for domain in SOURCE_RELIABILITY_TIER_2:
            if base_domain == domain or base_domain.endswith("." + domain):
                return 2

        # Default tier-3 (unranked/unknown)
        return 3

    def calculate_source_score(self, tier: int) -> float:
        """Convert source tier to normalized score (0-1 range).

        Normalizes using tier-1 as maximum (1.0).

        Args:
            tier: Source tier (1, 2, or 3)

        Returns:
            Normalized score between 0 and 1
        """
        from src.config import TIER_1_MULTIPLIER, TIER_2_MULTIPLIER, TIER_3_MULTIPLIER

        tier_multipliers = {
            1: TIER_1_MULTIPLIER,
            2: TIER_2_MULTIPLIER,
            3: TIER_3_MULTIPLIER,
        }

        multiplier = tier_multipliers.get(tier, TIER_3_MULTIPLIER)
        # Normalize to 0-1 range (tier-1 = 1.0)
        return multiplier / TIER_1_MULTIPLIER

    def strip_non_content_elements(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove navigation, ads, footers, and other non-article content.

        Args:
            soup: BeautifulSoup object of the full HTML page

        Returns:
            BeautifulSoup object with non-content elements removed
        """
        # Remove script and style elements
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        # Remove common non-content sections by tag and class patterns
        non_content_selectors = [
            "nav",
            "header",
            "footer",
            "aside",
            '[role="navigation"]',
            '[role="banner"]',
            '[role="contentinfo"]',
            '[class*="nav"]',
            '[class*="menu"]',
            '[class*="sidebar"]',
            '[class*="ad"]',
            '[class*="advertisement"]',
            '[class*="promo"]',
            '[class*="social"]',
            '[class*="share"]',
            '[class*="comment"]',
            '[class*="footer"]',
            '[class*="header"]',
            '[class*="cookie"]',
            '[id*="nav"]',
            '[id*="menu"]',
            '[id*="sidebar"]',
            '[id*="ad"]',
            '[id*="footer"]',
            '[id*="header"]',
        ]

        for selector in non_content_selectors:
            for element in soup.select(selector):
                element.decompose()

        for element in soup.select('[id*="cookie"], [class*="cookie"]'):
            element.decompose()

        return soup

    def enforce_source_diversity(self, ranked_articles: List[Dict]) -> List[Dict]:
        """Enforce source diversity cap by limiting articles per source.

        Ensures no single source dominates the top results by capping at
        MAX_ARTICLES_PER_SOURCE articles per source.

        Args:
            ranked_articles: List of article dicts sorted by overall_score (descending)

        Returns:
            Filtered list with source diversity enforced
        """
        from src.config import MAX_ARTICLES_PER_SOURCE

        source_counts = {}
        diverse_articles = []

        for item in ranked_articles:
            article_url = item.get("article", {}).get("url", "")
            if not article_url:
                diverse_articles.append(item)
                continue

            # Extract source domain
            source_domain = self.get_base_domain(article_url)
            if not source_domain:
                diverse_articles.append(item)
                continue

            # Check if source has reached cap
            current_count = source_counts.get(source_domain, 0)
            if current_count < MAX_ARTICLES_PER_SOURCE:
                diverse_articles.append(item)
                source_counts[source_domain] = current_count + 1
            else:
                logger.info(
                    f"Skipping article from {source_domain} (source cap reached: {MAX_ARTICLES_PER_SOURCE})"
                )

        return diverse_articles

    def _detect_paywall(self, soup: BeautifulSoup, url: str) -> bool:
        """Detect if the page has a paywall or requires subscription."""
        # Check URL domain
        domain = url.split("/")[2]
        if domain in self.paywall_domains:
            return True

        # Check for paywall indicators in text
        text = soup.get_text().lower()
        for pattern in self.paywall_patterns:
            if re.search(pattern, text):
                return True

        # Check for common paywall elements
        paywall_elements = soup.find_all(
            "div", class_=re.compile(r"paywall|subscription|premium|membership", re.I)
        )
        if not paywall_elements:
            paywall_elements = soup.find_all(
                "section",
                class_=re.compile(r"paywall|subscription|premium|membership", re.I),
            )
        if paywall_elements:
            return True

        return False

    def _is_thin_content(self, text: str, paragraph_count: int) -> bool:
        """Determine whether extracted text is too thin to trust."""
        if not text:
            return True
        if len(text.strip()) < MIN_EXTRACTED_TEXT_LENGTH:
            return True
        if paragraph_count < MIN_EXTRACTED_PARAGRAPHS:
            return True
        return False

    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """Fetch page HTML with requests to avoid Playwright when possible."""
        import requests

        headers = {
            "User-Agent": user_agent_pool.get_next(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text

    def _extract_with_trafilatura(self, html_content: str, url: str) -> Tuple[str, int]:
        global trafilatura
        if not trafilatura:
            try:
                trafilatura = importlib.import_module("trafilatura")
            except ImportError:
                return "", 0
        if not trafilatura:
            return "", 0
        extracted = getattr(trafilatura, "extract", None)
        if extracted is None:
            return "", 0
        extracted_content = extracted(
            html_content,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        text = extracted_content or ""
        paragraph_count = len([p for p in text.split("\n") if p.strip()])
        return text, paragraph_count

    def _extract_with_readability(self, html_content: str) -> Tuple[str, int]:
        global Document
        if not Document:
            try:
                Document = importlib.import_module("readability").Document
            except ImportError:
                return "", 0
        if not Document:
            return "", 0
        doc = Document(html_content)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text("\n")
        paragraph_count = len(soup.find_all("p"))
        return text, paragraph_count

    def _handle_paywalled_content(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """Attempt to handle paywalled content by extracting preview content."""
        try:
            # Look for preview or teaser content
            preview_selectors = [
                ".article-preview",
                ".teaser-content",
                ".article-summary",
                ".preview-content",
                '[class*="preview"]',
                '[class*="teaser"]',
                ".article-excerpt",
                ".summary",
            ]

            for selector in preview_selectors:
                preview = soup.select_one(selector)
                if preview:
                    return str(preview)

            # Try to get first few paragraphs
            paragraphs = soup.find_all("p")
            if paragraphs:
                preview_text = "\n\n".join(p.get_text() for p in paragraphs[:3])
                if len(preview_text) > 100:  # Ensure we have meaningful content
                    return preview_text

        except Exception as e:
            print(f"Preview extraction failed: {str(e)}")

        return None

    @retry_with_backoff(
        max_attempts=5, retry_on=(PlaywrightTimeoutError, PlaywrightError, Exception)
    )
    def _fetch_with_playwright(self, url: str) -> str:
        """Fetch article content using Playwright with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content string

        Raises:
            PlaywrightError: If fetch fails after all retries
        """
        print(f"Fetching content from: {url} using Edge")
        start_time = time.time()

        with sync_playwright() as p:
            # Launch Edge with new headless mode
            browser = p.chromium.launch(
                channel="msedge",
                headless=False,  # Disable headless mode
            )

            # Rotate user agent for this request
            current_user_agent = user_agent_pool.get_next()

            # Create a new context with rotated user agent
            context = browser.new_context(user_agent=current_user_agent)

            page = context.new_page()

            # Set extra headers
            page.set_extra_http_headers(
                {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            try:
                # Navigate to the page
                response = page.goto(url, timeout=45000, wait_until="domcontentloaded")

                # Check response status
                if not response or not response.ok:
                    status = response.status if response else "No response"
                    logger.warning(
                        "Playwright navigation failed for %s with status %s",
                        url,
                        status,
                    )
                    context.close()
                    browser.close()
                    raise PlaywrightError(
                        f"Failed to load page {url} with status {status}"
                    )

                # Wait for content to load
                try:
                    # Wait for main content to be visible
                    page.wait_for_selector(
                        "article, main, .article-content, .post-content, .entry-content",
                        timeout=15000,
                    )
                except PlaywrightTimeoutError:
                    print(
                        "Main content selector not found, continuing with full page content"
                    )
                    logger.info(
                        "Playwright content selector timeout for %s",
                        url,
                    )

                # Wait for network idle
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PlaywrightTimeoutError:
                    print("Network idle timeout, using current state")
                    logger.info("Playwright network idle timeout for %s", url)

                # Wait an additional 5 seconds to ensure dynamic content is loaded
                print("Waiting for dynamic content to load...")
                time.sleep(5)

                # Get the full page HTML content
                html_content = page.content()

                duration = time.time() - start_time
                logger.info(
                    "Playwright fetched %s bytes from %s in %.2fs",
                    len(html_content),
                    url,
                    duration,
                )
                print("HTML fetched successfully via Edge.")
                return html_content

            finally:
                context.close()
                browser.close()

    def fetch_article_content(
        self, url: str, article_id: str
    ) -> Optional[Dict[str, str]]:
        """Fetch article content with staged extraction and Playwright fallback."""
        last_error = None
        html_content = None
        extraction_method = None
        is_paywalled = False
        was_truncated = False
        test_mode = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules

        if not test_mode:
            try:
                html_content = self._fetch_with_requests(url)

                if ENABLE_GRACEFUL_DEGRADATION:
                    self.degradation_status.update_success()

            except Exception as e:
                print(f"Requests fetch failed for {url}: {str(e)}")
                logger.warning(f"Requests fetch failed for {url}: {str(e)}")
                last_error = e

        if not html_content:
            try:
                html_content = self._fetch_with_playwright(url)
                extraction_method = "playwright"
                if ENABLE_GRACEFUL_DEGRADATION:
                    self.degradation_status.update_success()
            except Exception as e:
                print(f"Playwright fetch failed for {url}: {str(e)}")
                logger.error(f"Content fetch failed for {url}: {str(e)}")
                last_error = e

                if ENABLE_GRACEFUL_DEGRADATION:
                    self.degradation_status.update_failure(
                        f"Content fetch failed for article {article_id}: {str(e)}"
                    )

        if not html_content:
            print(f"Failed to fetch content for {url} after all retry attempts.")

            retry_summary = retry_logger.get_session_summary()
            error_info = {
                "article_id": article_id,
                "url": url,
                "error_type": type(last_error).__name__
                if last_error
                else "UnknownError",
                "error_message": str(last_error)
                if last_error
                else "Failed to fetch content after retries",
                "timestamp": datetime.now().isoformat(),
                "fetch_method": extraction_method or "requests",
                "retry_metadata": {
                    "total_attempts": retry_summary["total_retries"],
                    "success_count": retry_summary["success_count"],
                    "failure_count": retry_summary["failure_count"],
                    "avg_wait_time": retry_summary["avg_wait_time"],
                    "total_cumulative_wait": retry_summary["total_cumulative_wait"],
                    "session_id": retry_logger.session_id,
                    "log_file": f"Output/retry_logs/{retry_logger.session_id}_retry_log.json",
                },
            }
            self._save_error_info(article_id, error_info)
            return None

        try:
            print("Extracting article content...")

            raw_html = html_content
            html_size = len(raw_html)
            soup = BeautifulSoup(html_content, "html.parser")

            block_type = BlockDetector.detect_block_type(html_content=html_content)
            if block_type == BlockType.SOFT_BLOCK:
                print("Soft block detected - escalating to Playwright")
                html_content = self._fetch_with_playwright(url)
                extraction_method = "playwright"
                soup = BeautifulSoup(html_content, "html.parser")

            is_paywalled = self._detect_paywall(soup, url)
            if is_paywalled:
                print("Paywall detected - attempting preview content extraction")
                preview_html = self._handle_paywalled_content(url, soup)
                if preview_html:
                    soup = BeautifulSoup(preview_html, "html.parser")

            if trafilatura is None:
                logger.warning("Trafilatura is not installed; skipping extractor")
            print("Extracting with trafilatura...")
            extracted_text, paragraph_count = self._extract_with_trafilatura(
                str(soup), url
            )
            extraction_method = extraction_method or "trafilatura"

            if self._is_thin_content(extracted_text, paragraph_count):
                print("Trafilatura extraction too thin - trying readability")
                if Document is None:
                    logger.warning(
                        "readability-lxml is not installed; skipping extractor"
                    )
                extracted_text, paragraph_count = self._extract_with_readability(
                    str(soup)
                )
                extraction_method = "readability"

            if self._is_thin_content(extracted_text, paragraph_count):
                paragraph_text = "\n".join(
                    p.get_text(strip=True) for p in soup.find_all("p")
                )
                if paragraph_text.strip():
                    extracted_text = paragraph_text
                    paragraph_count = len(soup.find_all("p"))
                    extraction_method = extraction_method or "soup_text"

            if self._is_thin_content(extracted_text, paragraph_count):
                print("Readability extraction too thin - using Playwright")
                html_content = self._fetch_with_playwright(url)
                soup = BeautifulSoup(html_content, "html.parser")
                extracted_text, paragraph_count = self._extract_with_trafilatura(
                    str(soup), url
                )
                extraction_method = "playwright"

            if not extracted_text:
                raise ValueError("Extraction produced no content")

            full_markdown = self.h2t.handle(extracted_text)
            markdown_size = len(full_markdown)

            if markdown_size > MAX_MARKDOWN_LENGTH:
                print(
                    f"Markdown size ({markdown_size} chars) exceeds limit ({MAX_MARKDOWN_LENGTH} chars) - truncating..."
                )
                full_markdown = (
                    full_markdown[:MAX_MARKDOWN_LENGTH] + TRUNCATION_INDICATOR
                )
                was_truncated = True

            conversion_metadata = {
                "success": True,
                "html_size": html_size,
                "markdown_size": len(full_markdown),
                "truncated": was_truncated,
                "is_paywalled": is_paywalled,
                "conversion_method": extraction_method,
                "timestamp": datetime.now().isoformat(),
            }

            content_dict = {
                "html": raw_html,
                "raw_markdown": full_markdown,
                "extracted_markdown": full_markdown,
                "url": url,
                "conversion_metadata": conversion_metadata,
            }
            self._save_article_content(article_id, content_dict)

            return content_dict

        except Exception as e:
            print(f"Markdown conversion failed: {str(e)}")
            logger.warning(
                f"Full extraction failed for {url}, using fallback: {str(e)}"
            )

            try:
                soup = BeautifulSoup(html_content, "html.parser")

                main_content = None
                main_selectors = [
                    "main",
                    "article",
                    '[role="main"]',
                    ".article-content",
                    ".post-content",
                ]
                for selector in main_selectors:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break

                if main_content:
                    fallback_markdown = self.h2t.handle(str(main_content))
                else:
                    body = soup.find("body")
                    fallback_markdown = self.h2t.handle(str(body)) if body else ""

                conversion_metadata = {
                    "success": True,
                    "html_size": len(html_content),
                    "markdown_size": len(fallback_markdown),
                    "truncated": False,
                    "is_paywalled": is_paywalled,
                    "conversion_method": "fallback_main_body",
                    "fallback_reason": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

                content_dict = {
                    "html": html_content,
                    "raw_markdown": fallback_markdown,
                    "extracted_markdown": fallback_markdown,
                    "url": url,
                    "conversion_metadata": conversion_metadata,
                }
                self._save_article_content(article_id, content_dict)

                return content_dict

            except Exception as fallback_error:
                print(f"Fallback extraction also failed: {str(fallback_error)}")
                error_info = {
                    "article_id": article_id,
                    "url": url,
                    "error_type": "ConversionError",
                    "error_message": f"Both full conversion and fallback failed: {str(e)}, {str(fallback_error)}",
                    "timestamp": datetime.now().isoformat(),
                    "fetch_method": extraction_method or "requests",
                }
                self._save_error_info(article_id, error_info)
                return None

    def _save_error_info(self, article_id: str, error_info: Dict):
        """Saves error information to a JSON file."""
        try:
            error_dir = os.path.join(self.content_dir, "errors")
            os.makedirs(error_dir, exist_ok=True)
            # Use a more specific error filename if article_id is available
            filename = (
                f"error_{article_id}.json"
                if article_id
                else f"error_{int(time.time())}.json"
            )
            error_file = os.path.join(error_dir, filename)
            with open(error_file, "w", encoding="utf-8") as f:
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
            with open(
                os.path.join(article_dir, "content.html"), "w", encoding="utf-8"
            ) as f:
                f.write(content["html"])

            # Save markdown content
            with open(
                os.path.join(article_dir, "content.md"), "w", encoding="utf-8"
            ) as f:
                f.write(content["extracted_markdown"])

            # Save metadata with conversion info
            metadata = {
                "url": content["url"],
                "fetch_time": datetime.now().isoformat(),
                "content_length": len(content["extracted_markdown"]),
            }

            # Add conversion metadata if available
            if "conversion_metadata" in content:
                metadata["conversion"] = content["conversion_metadata"]

            with open(
                os.path.join(article_dir, "metadata.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            print(f"Error saving article content: {str(e)}")

    def analyze_article(self, article):
        """Analyze a single article for relevance based on keywords and trending factors."""
        scores = {}
        article_title = article.get("title", "").lower()
        article_desc = article.get("snippet", "").lower()
        article_url = article.get("url", "")

        for category, keywords in self.keywords.items():
            category_score = 0
            for keyword in keywords:
                title_score = fuzz.partial_ratio(keyword.lower(), article_title)
                desc_score = fuzz.partial_ratio(keyword.lower(), article_desc)
                category_score = max(category_score, (title_score + desc_score) / 2)
            scores[category] = category_score / 100.0

        # Calculate keyword score
        keyword_score = max(scores.values()) if scores else 0.0

        # Calculate trending score
        trending_score = self.calculate_trending_score(
            article, [article]
        )  # Pass single article for initial scoring

        # Calculate source reliability score (T016-T017)
        source_tier = self.get_source_tier(article_url) if article_url else 3
        source_score = self.calculate_source_score(source_tier)

        relevance_score = self.calculate_relevance_score(article, source_score)

        # Weight the scores using config (50% keywords, 30% trending, 20% source)
        overall_score = (
            SCORE_WEIGHT_KEYWORD * keyword_score
            + SCORE_WEIGHT_TRENDING * trending_score
            + SCORE_WEIGHT_SOURCE * source_score
        )
        overall_score = overall_score * (0.7 + 0.3 * relevance_score)

        # Determine primary category
        primary_category = "Other"
        if scores:
            primary_category = max(scores.items(), key=lambda item: item[1])[0]
            if (
                scores[primary_category] < 0.1
            ):  # Threshold for meaningful category assignment
                primary_category = "Other"

        return {
            "scores": scores,
            "insights": None,  # Initialize insights as None
            "trending_score": trending_score,
            "keyword_score": keyword_score,
            "source_tier": source_tier,  # T016: Store source tier
            "source_score": source_score,  # T017: Store source score
            "relevance_score": relevance_score,
            "overall_score": overall_score,
            "primary_category": primary_category,
        }

    def calculate_relevance_score(self, article: Dict, source_score: float) -> float:
        title = article.get("title", "")
        snippet = article.get("snippet", "")
        combined = f"{title} {snippet}".strip().lower()
        tokens = [token for token in re.split(r"\W+", combined) if token]
        token_count = max(len(tokens), 1)

        keyword_matches = 0
        for keywords in self.keywords.values():
            for keyword in keywords:
                if keyword.lower() in combined:
                    keyword_matches += 1

        keyword_density_score = min(keyword_matches / token_count * 10, 1.0)

        recency_score = 0.5
        article_time_str = article.get("published_time", "")
        if article_time_str and article_time_str != "Unknown Time":
            try:
                article_time = datetime.fromisoformat(
                    article_time_str.replace("Z", "+00:00")
                )
                if article_time.tzinfo is None:
                    article_time = article_time.replace(tzinfo=timezone.utc)
                now_aware = datetime.now(timezone.utc)
                time_diff = now_aware - article_time
                recency_score = max(
                    1 - (time_diff.total_seconds() / (7 * 24 * 3600)), 0
                )
            except ValueError:
                recency_score = 0.5

        duplicate_penalty = 1.0 if article.get("is_duplicate") else 0.0

        relevance_score = (
            RELEVANCE_KEYWORD_DENSITY_WEIGHT * keyword_density_score
            + RELEVANCE_RECENCY_WEIGHT * recency_score
            + RELEVANCE_SOURCE_WEIGHT * source_score
            - RELEVANCE_DUPLICATE_PENALTY_WEIGHT * duplicate_penalty
        )

        return max(min(relevance_score, 1.0), 0.0)

    def get_llm_insights(self, article_data: Dict) -> Optional[str]:
        """Get LLM-generated insights for a single article's content."""
        try:
            if not USE_LLM:
                return None

            if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
                return article_data.get("snippet") or "Test insight (stub)"

            content = article_data.get("description") or article_data.get(
                "snippet", "No Description"
            )

            insights_result = self.llm_chain.invoke(
                {"title": article_data.get("title", "No Title"), "description": content}
            )

            # Handle different response types
            if hasattr(insights_result, "content"):
                return str(insights_result.content)
            else:
                return str(insights_result)

        except Exception as e:
            print(
                f"Error getting LLM insights for article '{article_data.get('title', 'Unknown')}': {e}"
            )
            return None

    def rank_articles(self, articles, top_n=20):
        """Rank articles based on relevance scores and trending factors, ensuring minimum Fintech articles."""
        print(f"\n--- Starting Article Analysis ---")
        print(f"Analyzing {len(articles)} unique articles for initial scoring...")

        # First pass: analyze all articles
        analyzed_articles = []
        for i, article in enumerate(articles):
            if (i + 1) % 50 == 0:
                print(f"  Scored {i + 1}/{len(articles)} articles...")
            analysis = self.analyze_article(article)
            analyzed_articles.append({"article": article, "analysis": analysis})
        print("Initial scoring complete.")

        # Update trending scores with full article context
        print("Updating trending scores with full article context...")
        from src.config import (
            SCORE_WEIGHT_KEYWORD,
            SCORE_WEIGHT_TRENDING,
            SCORE_WEIGHT_SOURCE,
        )

        for item in analyzed_articles:
            article = item["article"]
            trending_score = self.calculate_trending_score(article, articles)
            # Update overall score with new trending score and source reliability (T018)
            # New formula: 50% keyword + 30% trending + 20% source
            keyword_score = item["analysis"]["keyword_score"]
            source_score = item["analysis"]["source_score"]
            relevance_score = item["analysis"].get("relevance_score", 0.0)

            item["analysis"]["trending_score"] = trending_score
            item["analysis"]["relevance_score"] = relevance_score
            base_score = (
                SCORE_WEIGHT_KEYWORD * keyword_score
                + SCORE_WEIGHT_TRENDING * trending_score
                + SCORE_WEIGHT_SOURCE * source_score
            )
            item["analysis"]["overall_score"] = base_score * (
                0.7 + 0.3 * relevance_score
            )

        # Sort all articles by overall score
        sorted_articles = sorted(
            analyzed_articles,
            key=lambda x: (
                x["analysis"]["overall_score"],
                x["analysis"].get("relevance_score", 0.0),
            ),
            reverse=True,
        )

        # Select initial top_n articles
        selected_articles = sorted_articles[:top_n]

        # Count Fintech articles in selection
        fintech_count = sum(
            1
            for item in selected_articles
            if item["analysis"]["primary_category"] == "Fintech"
        )

        # If we need more Fintech articles
        if fintech_count < 3:
            print(f"\n--- Adjusting for minimum Fintech articles ---")
            print(f"Current Fintech count: {fintech_count}, target: 3")

            # Get remaining articles (those not in top_n)
            remaining_articles = sorted_articles[top_n:]

            # Find Fintech articles from remaining pool
            available_fintech = [
                item
                for item in remaining_articles
                if item["analysis"]["primary_category"] == "Fintech"
            ]

            # Sort available Fintech articles by score
            available_fintech.sort(
                key=lambda x: x["analysis"]["overall_score"], reverse=True
            )

            # Find non-Fintech articles in selection that can be replaced
            replaceable_articles = [
                item
                for item in selected_articles
                if item["analysis"]["primary_category"] != "Fintech"
            ]

            # Sort replaceable articles by score (lowest first)
            replaceable_articles.sort(key=lambda x: x["analysis"]["overall_score"])

            # Perform replacements
            while fintech_count < 3 and available_fintech and replaceable_articles:
                # Remove lowest scoring non-Fintech article
                removed = replaceable_articles.pop(0)
                selected_articles.remove(removed)

                # Add highest scoring available Fintech article
                added = available_fintech.pop(0)
                selected_articles.append(added)

                fintech_count += 1
                print(
                    f"Replaced article '{removed['article'].get('title', '')[:50]}...' with Fintech article '{added['article'].get('title', '')[:50]}...'"
                )

            # Re-sort the final selection
            selected_articles.sort(
                key=lambda x: x["analysis"]["overall_score"], reverse=True
            )

            print(f"Final Fintech count: {fintech_count}")

        # Enforce source diversity (T021) - AFTER category enforcement
        print(f"\n--- Enforcing Source Diversity ---")
        pre_diversity_count = len(selected_articles)
        selected_articles = self.enforce_source_diversity(selected_articles)
        post_diversity_count = len(selected_articles)

        if pre_diversity_count != post_diversity_count:
            print(
                f"Diversity enforcement: {pre_diversity_count} -> {post_diversity_count} articles"
            )
        else:
            print(f"No articles removed by diversity enforcement")

        # Log score breakdowns for audit trail (T022)
        print(f"\n--- Score Breakdown (Top 10) ---")
        for i, item in enumerate(selected_articles[:10], 1):
            analysis = item["analysis"]
            article = item["article"]
            logger.info(
                f"Rank #{i}: {article.get('title', '')[:60]}... | "
                f"Overall: {analysis['overall_score']:.3f} | "
                f"Relevance: {analysis.get('relevance_score', 0.0):.3f} | "
                f"Keyword: {analysis['keyword_score']:.3f} | "
                f"Trending: {analysis['trending_score']:.3f} | "
                f"Source: {analysis['source_score']:.3f} (Tier-{analysis['source_tier']}) | "
                f"Category: {analysis['primary_category']}"
            )
            print(
                f"  #{i}: Score={analysis['overall_score']:.3f} "
                f"(R:{analysis.get('relevance_score', 0.0):.2f} "
                f"K:{analysis['keyword_score']:.2f} T:{analysis['trending_score']:.2f} "
                f"S:{analysis['source_score']:.2f}/Tier-{analysis['source_tier']}) "
                f"- {article.get('title', '')[:50]}..."
            )

        # Initialize result list and tracking variables
        successful_articles = []
        articles_to_try = selected_articles.copy()
        attempts = 0
        max_attempts = min(
            len(sorted_articles), top_n * 3
        )  # Try up to 3x the target, or all available

        print(f"\n--- Fetching Content for Top Articles ---")
        print(f"Target: {top_n} articles with content")
        print(f"Available articles pool: {len(sorted_articles)}")

        # Keep trying articles until we have enough successful fetches or run out of articles
        article_index = 0
        test_mode = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules

        while (
            len(successful_articles) < top_n
            and article_index < len(sorted_articles)
            and attempts < max_attempts
        ):
            attempts += 1

            # Get the next article to try
            if article_index >= len(articles_to_try):
                # We've exhausted the initial selection, try from remaining sorted articles
                remaining = [a for a in sorted_articles if a not in articles_to_try]
                if not remaining:
                    print(f"\nNo more articles available to try")
                    break
                articles_to_try.extend(remaining)

            item = articles_to_try[article_index]
            article_index += 1

            article = item.get("article")
            analysis = item.get("analysis")

            # Basic validation
            if not article or not analysis:
                print(f"Warning: Skipping invalid article")
                continue

            print(
                f"\nAttempt {attempts}: Processing article {len(successful_articles) + 1}/{top_n}"
            )
            print(f"Article: {article.get('title', 'Unknown Title')[:80]}...")
            print(f"Category: {analysis.get('primary_category', 'Unknown')}")
            print(f"Score: {analysis.get('overall_score', 0):.3f}")

            # Generate article ID
            safe_title = re.sub(r"[^\w\-]+", "_", article.get("title", "untitled")[:30])
            article_id = (
                f"{len(successful_articles) + 1:02d}_{safe_title}_{int(time.time())}"
            )

            # Attempt to fetch content
            article_url = article.get("url")
            if not article_url:
                print("No URL found - skipping to next article")
                continue

            print(f"Fetching content from: {article_url}")
            if test_mode:
                logger.info(
                    "Test mode enabled - skipping live fetch for %s", article_url
                )
                stub_text = f"{article.get('title', '')} {article.get('snippet', '')}"
                content_result = {
                    "html": "",
                    "raw_markdown": stub_text,
                    "extracted_markdown": stub_text,
                    "url": article_url,
                    "conversion_metadata": {
                        "success": True,
                        "html_size": 0,
                        "markdown_size": len(stub_text),
                        "truncated": False,
                        "is_paywalled": False,
                        "conversion_method": "test_stub",
                        "timestamp": datetime.now().isoformat(),
                    },
                }
            else:
                content_result = self.fetch_article_content(article_url, article_id)

            if test_mode:
                content_ok = bool(
                    content_result and "extracted_markdown" in content_result
                )
            else:
                content_ok = (
                    content_result
                    and "extracted_markdown" in content_result
                    and len(content_result["extracted_markdown"].strip()) > 100
                )

            if content_ok:
                # Content fetch successful
                print("[OK] Content fetched successfully")
                item["article"]["fetched_content"] = content_result

                # Get LLM insights if enabled and content is substantial
                if USE_LLM and analysis.get("overall_score", 0) >= LLM_THRESHOLD:
                    print(f"Getting LLM insights...")
                    description = ""
                    if content_result and "extracted_markdown" in content_result:
                        description = content_result["extracted_markdown"]
                    insights = self.get_llm_insights(
                        {
                            "title": article.get("title", ""),
                            "description": description,
                        }
                    )
                    item["analysis"]["insights"] = insights
                    if insights:
                        print("[OK] LLM insights generated successfully")
                    else:
                        print("[WARN] LLM insights generation failed")
                else:
                    print("Skipping LLM insights (disabled or low score)")
                    item["analysis"]["insights"] = None

                successful_articles.append(item)
                print(
                    f"[OK] Article {len(successful_articles)}/{top_n} added to results"
                )
            else:
                print(
                    "[WARN] Failed to fetch meaningful content - trying next highest-scoring article"
                )

        # Summary
        print("\n--- Content Fetching Summary ---")
        print(f"Total attempts: {attempts}")
        print(
            f"Successfully fetched content for {len(successful_articles)}/{top_n} articles"
        )

        # Category distribution in final results
        category_counts = {}
        for item in successful_articles:
            category = item["analysis"]["primary_category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        print("\n--- Final Category Distribution ---")
        for category, count in category_counts.items():
            print(f"{category}: {count} articles")

        if len(successful_articles) < top_n:
            print(
                f"\nWarning: Only found {len(successful_articles)} articles with valid content"
            )
            print(
                "Consider adjusting search criteria or increasing the source article pool"
            )

        return successful_articles

    def remove_duplicates(self, articles, threshold=75):
        """Remove duplicate articles based on title similarity and canonical URL."""
        unique_articles = []
        seen_titles = set()
        seen_urls = set()

        for article in articles:
            title = article.get("title", "")
            canonical_url = article.get("canonical_url") or article.get("url")
            is_duplicate = False

            if canonical_url:
                normalized = normalize_url(canonical_url)
                if normalized and normalized in seen_urls:
                    is_duplicate = True
                elif normalized:
                    article["canonical_url"] = normalized

            if not is_duplicate:
                if title in seen_titles:
                    is_duplicate = True
                else:
                    for unique in unique_articles:
                        similarity = fuzz.ratio(title, unique.get("title", ""))
                        if similarity > threshold:
                            is_duplicate = True
                            break

            article["is_duplicate"] = is_duplicate

            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(title)
                if canonical_url:
                    normalized = normalize_url(canonical_url)
                    if normalized:
                        seen_urls.add(normalized)

        return unique_articles

    def calculate_trending_score(
        self, article: Dict, all_articles: List[Dict]
    ) -> float:
        """Calculate trending score based on frequency, time, and source reliability"""
        # Calculate frequency score (how many similar articles exist)
        frequency_score = 0
        article_title_lower = article.get("title", "").lower()
        for other_article in all_articles:
            if other_article != article:
                similarity = fuzz.ratio(
                    article_title_lower, other_article.get("title", "").lower()
                )
                if similarity > 60:  # Lower threshold for counting related articles
                    frequency_score += 1
        frequency_score = min(frequency_score / 10, 1.0)  # Normalize to 0-1

        # Calculate time score (how recent the article is)
        time_score = 0.5  # Default score for unknown times
        article_time_str = article.get("published_time", "")
        try:
            if article_time_str and article_time_str != "Unknown Time":
                # Try different date formats
                try:
                    # Try ISO format first
                    article_time = datetime.fromisoformat(
                        article_time_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    # If ISO format fails, try to parse relative time
                    current_time = datetime.now(timezone.utc)
                    if "hour" in article_time_str.lower():
                        hours = int("".join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(hours=hours)
                    elif "day" in article_time_str.lower():
                        days = int("".join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(days=days)
                    elif "minute" in article_time_str.lower():
                        minutes = int("".join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(minutes=minutes)
                    elif "week" in article_time_str.lower():
                        weeks = int("".join(filter(str.isdigit, article_time_str)))
                        article_time = current_time - timedelta(weeks=weeks)
                    else:
                        raise ValueError(
                            f"Unrecognized time format: {article_time_str}"
                        )

                # Make datetime aware if it's naive
                if article_time.tzinfo is None:
                    article_time = article_time.replace(tzinfo=timezone.utc)

                # Calculate time score
                now_aware = datetime.now(timezone.utc)
                time_diff = now_aware - article_time
                time_score = max(
                    1 - (time_diff.total_seconds() / (7 * 24 * 3600)), 0
                )  # 7 days window

        except Exception as e:
            print(
                f"Notice: Using default time score for '{article_time_str}'. Reason: {str(e)}"
            )
            # Keep using default time_score of 0.5

        # Calculate source reliability score
        trusted_sources = [
            "Reuters",
            "Bloomberg",
            "Financial Times",
            "Wall Street Journal",
            "TechCrunch",
            "Wired",
            "MIT Technology Review",
            "Harvard Business Review",
        ]
        source = article.get("source", "").lower()
        source_score = 0.8  # Default score
        for trusted in trusted_sources:
            if trusted.lower() in source:
                source_score = 1.0
                break

        # Combine scores with weights
        trending_score = (
            (0.2 * time_score) + (0.3 * frequency_score) + (0.5 * source_score)
        )
        return trending_score

    def generate_topic_summary(self, top_articles: List[Dict]) -> Dict:
        """Generate a summary of top AI and fintech news by topic"""
        # Group articles by their highest scoring category
        articles_by_category = {
            "AI Development": [],
            "Fintech": [],
            "GenAI Usage": [],
            "Other": [],
        }

        for item in top_articles:
            scores = item["analysis"]["scores"]
            if not scores:  # Handle case where scores might be empty
                articles_by_category["Other"].append(item)
                continue

            # Find the category with the highest score
            top_category = max(scores.items(), key=lambda item: item[1])[0]

            # Assign to category if score is meaningful, otherwise 'Other'
            # You might want a threshold here, e.g., max score > 0.2
            if scores[top_category] > 0.1:  # Example threshold
                if top_category in articles_by_category:
                    articles_by_category[top_category].append(item)
                else:
                    articles_by_category["Other"].append(
                        item
                    )  # Should not happen with current keywords
            else:
                articles_by_category["Other"].append(item)

        return {
            "top_articles": top_articles,  # Pass the original list containing analysis etc.
            "ai_development_count": len(articles_by_category["AI Development"]),
            "fintech_count": len(articles_by_category["Fintech"]),
            "genai_usage_count": len(articles_by_category["GenAI Usage"]),
            "other_count": len(articles_by_category["Other"]),
            "top_impact": self._get_high_impact_articles(
                top_articles
            ),  # Use overall_score now
        }

    def _get_high_impact_articles(self, articles: List[Dict]) -> List[Dict]:
        """Extract top 3 articles based on overall_score"""
        # Sort by 'overall_score' found within the 'analysis' dictionary
        articles.sort(
            key=lambda x: x.get("analysis", {}).get("overall_score", 0), reverse=True
        )
        # Return the top 3 items (which contain both 'article' and 'analysis')
        return articles[:3]
