"""Module for analyzing news article content."""

import re
from typing import List, Dict, Optional
from datetime import datetime
from fuzzywuzzy import fuzz
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.models import ArticleAnalysis, TrendAnalysis
from src.config import OPENAI_API_KEY, OPENAI_API_BASE, USE_LLM, LLM_THRESHOLD

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
        
        self.keywords = {
            'AI Development': [
                'artificial intelligence research', 'machine learning advances',
                'AI breakthroughs', 'neural networks', 'deep learning'
            ],
            'Fintech': [
                'digital banking', 'blockchain finance', 'payment technology',
                'financial technology', 'cryptocurrency'
            ],
            'GenAI Usage': [
                'generative AI', 'AI applications', 'AI implementation',
                'AI automation', 'AI tools'
            ]
        }
        # Define the prompt template once
        self.llm_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert news analyst. Analyze the article and provide key insights."),
            ("user", "Article Title: {title}\nDescription: {description}\n\nProvide a brief analysis of this article's significance (2-3 sentences).")
        ])
        self.llm_chain = self.llm_prompt | self.llm

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
            # Check if LLM usage is enabled and score meets threshold (optional check here)
            # This check might be redundant if we only call this for top articles anyway,
            # but keeps the logic clear if USE_LLM is False.
            if not USE_LLM: # Check the global flag
                 return None

            insights_result = self.llm_chain.invoke({
                "title": article_data.get('title', 'No Title'),
                "description": article_data.get('snippet', 'No Description') # Use 'snippet'
            })
            return str(insights_result.content)
        except Exception as e:
            print(f"Error getting LLM insights for article '{article_data.get('title', 'Unknown')}': {e}")
            return None # Return None if LLM call fails

    def rank_articles(self, articles, top_n=20):
        """Rank articles based on relevance scores, get LLM insights for top N, return top N."""
        print(f"Analyzing {len(articles)} unique articles for initial scoring...")
        analyzed_articles = []
        for i, article in enumerate(articles):
            if (i + 1) % 50 == 0: # Print progress
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
        print(f"\nSelected top {len(top_articles_to_analyze)} articles for LLM analysis.")

        # Get LLM insights ONLY for the top N articles if USE_LLM is True
        if USE_LLM:
            for i, item in enumerate(top_articles_to_analyze):
                 if (i + 1) % 5 == 0: # Print progress
                     print(f"  Getting LLM insights for article {i+1}/{len(top_articles_to_analyze)}...")
                 article_content = item['article']
                 # Only call LLM if overall score meets threshold
                 if item['analysis']['overall_score'] >= LLM_THRESHOLD:
                     insights = self.get_llm_insights(article_content)
                     item['analysis']['insights'] = insights
                 else:
                     item['analysis']['insights'] = None # Ensure it's None if threshold not met
            print("LLM analysis complete for top articles.")
        else:
             print("LLM analysis skipped (USE_LLM is False or no articles met threshold).")


        # Return only the top N articles with potentially added insights
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
        trending_score = (0.5 * time_score) + (0.3 * frequency_score) + (0.2 * source_score)
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