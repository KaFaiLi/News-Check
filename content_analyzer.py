from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.embeddings import OpenAIEmbeddings
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from fuzzywuzzy import fuzz
import numpy as np
from config import OPENAI_API_KEY, OPENAI_API_BASE

class ArticleAnalysis(BaseModel):
    relevance_score: float = Field(description="Relevance score from 0-1")
    banking_relevance: str = Field(description="Why this article matters to banking auditors")
    key_points: List[str] = Field(description="Key points from the article")

class ContentAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="openai/gpt-4o-mini",
            temperature=0.2,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE
        )
        self.structured_llm = self.llm.with_structured_output(ArticleAnalysis)
        self.analysis_prompt = "Article Title: {title}\nSource: {source}\nDate: {date}\nContent: {content}\n\nAs an AI expert specializing in financial services and banking regulations, analyze this article's relevance for banking auditors focusing on AI developments."

    def analyze_article(self, article: Dict) -> Optional[ArticleAnalysis]:
        """Analyze a single article for relevance and key points"""
        try:
            formatted_prompt = self.analysis_prompt.format(
                title=article['title'],
                source=article.get('source', 'Unknown'),
                date=article.get('published_time', 'Unknown'),
                content=article.get('snippet', '')
            )
            return self.structured_llm.invoke(formatted_prompt)
        except Exception as e:
            print(f"Error analyzing article: {str(e)}")
            return None

    def remove_duplicates(self, articles: List[Dict], threshold: int = 85) -> List[Dict]:
        """Remove duplicate articles based on title similarity"""
        unique_articles = []
        for article in articles:
            is_duplicate = False
            for unique_article in unique_articles:
                similarity = fuzz.ratio(article['title'].lower(), unique_article['title'].lower())
                if similarity > threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_articles.append(article)
        return unique_articles

    def get_article_embedding(self, article: Dict) -> np.ndarray:
        """Get embedding for an article using title and snippet"""
        text = f"{article['title']} {article.get('snippet', '')}"
        return self.embeddings.embed_query(text)

    def calculate_trending_score(self, article: Dict, all_articles: List[Dict], time_weight: float = 0.6) -> float:
        """Calculate trending score based on frequency and time-based analysis"""
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

        # Combine scores with weights
        trending_score = (time_weight * time_score) + ((1 - time_weight) * frequency_score)
        return trending_score

    def rank_articles(self, articles: List[Dict]) -> List[Dict]:
        """Rank articles based on trending score and relevance"""
        # First remove duplicates
        unique_articles = self.remove_duplicates(articles)
        
        # Calculate trending scores and analyze articles
        analyzed_articles = []
        for article in unique_articles:
            analysis = self.analyze_article(article)
            if analysis:
                article['analysis'] = analysis
                article['relevance_score'] = analysis.relevance_score
                article['trending_score'] = self.calculate_trending_score(article, unique_articles)
                # Combined score weighs both trending and relevance
                article['final_score'] = 0.7 * article['trending_score'] + 0.3 * article['relevance_score']
                analyzed_articles.append(article)

        # Sort by final score
        analyzed_articles.sort(key=lambda x: x['final_score'], reverse=True)
        return analyzed_articles[:10]  # Return top 10 articles

    def generate_quarterly_summary(self, top_articles: List[Dict]) -> Dict:
        """Generate a quarterly summary from top articles"""
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI expert creating a quarterly summary of AI developments for banking auditors."),
            ("user", "Based on the following top articles, generate a quarterly summary with key trends and implications:\n{articles}")
        ])

        articles_text = "\n\n".join([f"Title: {a['title']}\nKey Points: {a['analysis'].key_points}" for a in top_articles])
        messages = summary_prompt.format_messages(articles=articles_text)
        response = self.llm.invoke(messages)

        return {
            'executive_summary': response.content.split('\n')[:5],  # First 5 lines as executive summary
            'top_articles': top_articles
        }