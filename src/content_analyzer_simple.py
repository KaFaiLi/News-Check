"""Module for analyzing news article content."""

import re
from typing import List, Dict, Optional
from datetime import datetime
from fuzzywuzzy import fuzz
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from models import ArticleAnalysis, TrendAnalysis
from config import OPENAI_API_KEY, OPENAI_API_BASE, USE_LLM, LLM_THRESHOLD

class ContentAnalyzerSimple:
    def __init__(self):
        """Initialize the content analyzer."""
        print("Initializing ContentAnalyzer with LLM support")
        
        self.llm = ChatOpenAI(
            model="openai/gpt-3.5-turbo",
            temperature=0.7,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            headers={
                "HTTP-Referer": "https://github.com/News-Check",
                "X-Title": "News-Check"
            }
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

    def analyze_article(self, article):
        """Analyze a single article for relevance to keywords and generate insights."""
        scores = {}
        for category, keywords in self.keywords.items():
            category_score = 0
            for keyword in keywords:
                title_score = fuzz.partial_ratio(keyword.lower(), article['title'].lower())
                desc_score = fuzz.partial_ratio(keyword.lower(), article['description'].lower())
                category_score = max(category_score, (title_score + desc_score) / 2)
            scores[category] = category_score / 100.0

        # Get LLM analysis if any category score exceeds threshold
        insights = None
        if max(scores.values()) >= LLM_THRESHOLD:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert news analyst. Analyze the article and provide key insights."),
                ("user", "Article Title: {title}\nDescription: {description}\n\nProvide a brief analysis of this article's significance (2-3 sentences).")
            ])
            
            chain = prompt | self.llm
            insights = chain.invoke({
                "title": article['title'],
                "description": article['description']
            })

        return {
            'scores': scores,
            'insights': str(insights) if insights else None,
            'overall_score': max(scores.values())
        }

    def rank_articles(self, articles):
        """Rank articles based on relevance scores and return top articles."""
        analyzed_articles = []
        for article in articles:
            analysis = self.analyze_article(article)
            analyzed_articles.append({
                'article': article,
                'analysis': analysis
            })
        
        # Sort by overall score
        return sorted(analyzed_articles, key=lambda x: x['analysis']['overall_score'], reverse=True)

    def remove_duplicates(self, articles, threshold=85):
        """Remove duplicate articles based on title similarity."""
        unique_articles = []
        for article in articles:
            is_duplicate = False
            for unique in unique_articles:
                similarity = fuzz.ratio(article['title'], unique['title'])
                if similarity > threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_articles.append(article)
        return unique_articles

    def calculate_trending_score(self, article: Dict, all_articles: List[Dict]) -> float:
        """Calculate trending score based on frequency, time, and source reliability"""
        # Calculate frequency score (how many similar articles exist)
        frequency_score = 0
        for other_article in all_articles:
            if other_article != article:
                similarity = fuzz.ratio(article['title'].lower(), other_article['title'].lower())
                if similarity > 60:  # Lower threshold for counting related articles
                    frequency_score += 1
        frequency_score = min(frequency_score / 10, 1.0)  # Normalize to 0-1

        # Calculate time score (how recent the article is)
        try:
            article_time = datetime.fromisoformat(article.get('published_time', datetime.now().isoformat()))
            time_diff = datetime.now() - article_time
            time_score = max(1 - (time_diff.total_seconds() / (7 * 24 * 3600)), 0)  # 7 days window
        except:
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
        # Group articles by category
        ai_dev_articles = [a for a in top_articles if a['category'] == 'AI Development']
        fintech_articles = [a for a in top_articles if a['category'] == 'Fintech']
        genai_articles = [a for a in top_articles if a['category'] == 'GenAI Usage']
        
        return {
            'top_articles': top_articles,
            'ai_development_count': len(ai_dev_articles),
            'fintech_count': len(fintech_articles),
            'genai_usage_count': len(genai_articles),
            'top_impact': self._get_high_impact_articles(top_articles)
        }
    
    def _get_high_impact_articles(self, articles):
        """Extract high impact articles across categories"""
        high_impact = [a for a in articles if a['impact_level'] == 'High']
        high_impact.sort(key=lambda x: x['final_score'], reverse=True)
        return high_impact[:3]  # Return top 3 high impact articles 