from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.embeddings import OpenAIEmbeddings
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from fuzzywuzzy import fuzz
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ArticleAnalysis(BaseModel):
    relevance_score: float = Field(description="Relevance score from 0-1")
    banking_relevance: str = Field(description="Why this article matters to banking auditors")
    key_points: List[str] = Field(description="Key points from the article")

class ContentAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="openai/gpt-4o-mini",
            temperature=0.2,
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE')
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE')
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

    def cluster_articles(self, articles: List[Dict], n_clusters: int = 10) -> List[Dict]:
        """Cluster articles using embeddings and select representatives"""
        if len(articles) <= n_clusters:
            return articles

        # Get embeddings for all articles
        embeddings = [self.get_article_embedding(article) for article in articles]
        embeddings_array = np.array(embeddings)

        # Perform clustering
        kmeans = KMeans(n_clusters=min(n_clusters, len(articles)), random_state=42)
        cluster_labels = kmeans.fit_predict(embeddings_array)

        # Select representative articles from each cluster
        representatives = []
        for i in range(max(cluster_labels) + 1):
            cluster_articles = [article for j, article in enumerate(articles) if cluster_labels[j] == i]
            if cluster_articles:
                # Select article closest to cluster center
                cluster_center = kmeans.cluster_centers_[i]
                similarities = cosine_similarity([cluster_center], embeddings_array[cluster_labels == i])[0]
                representative = cluster_articles[np.argmax(similarities)]
                representatives.append(representative)

        return representatives

    def rank_articles(self, articles: List[Dict]) -> List[Dict]:
        """Rank articles based on clustering and relevance"""
        # First remove duplicates
        unique_articles = self.remove_duplicates(articles)
        
        # Cluster articles to get representatives
        clustered_articles = self.cluster_articles(unique_articles)
        
        # Analyze representative articles
        analyzed_articles = []
        for article in clustered_articles:
            analysis = self.analyze_article(article)
            if analysis:
                article['analysis'] = analysis
                article['relevance_score'] = analysis.relevance_score
                analyzed_articles.append(article)

        # Sort by relevance score
        analyzed_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
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