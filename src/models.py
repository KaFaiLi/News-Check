"""Pydantic models for structured output parsing."""

from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime

class ArticleAnalysis(BaseModel):
    """Model for individual article analysis."""
    relevance_score: float
    category: str
    impact_level: str
    key_points: List[str]
    industry_impact: str
    future_implications: str

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "relevance_score": 0.85,
                "category": "AI Development",
                "impact_level": "High",
                "key_points": ["Key point 1", "Key point 2", "Key point 3"],
                "industry_impact": "Significant impact on AI industry",
                "future_implications": "Potential future developments"
            }]
        }
    }

class TrendAnalysis(BaseModel):
    """Model for trend analysis of multiple articles."""
    key_trends: List[str]
    industry_developments: List[str]
    future_outlook: str
    category_insights: Dict[str, List[str]]

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "key_trends": ["Trend 1", "Trend 2", "Trend 3"],
                "industry_developments": ["Development 1", "Development 2"],
                "future_outlook": "Positive outlook for the industry",
                "category_insights": {
                    "AI Development": ["Insight 1", "Insight 2"],
                    "Fintech": ["Insight 1", "Insight 2"],
                    "GenAI Usage": ["Insight 1", "Insight 2"]
                }
            }]
        }
    }

class BriefSummary(BaseModel):
    """Model for brief article summary."""
    title: str
    summary: str
    significance: str
    image_url: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "title": "Article Title",
                "summary": "Brief summary of the article",
                "significance": "Why this article matters",
                "image_url": "https://example.com/image.jpg"
            }]
        }
    }

class DetailedReport(BaseModel):
    """Model for detailed article report."""
    title: str
    category: str
    analysis: ArticleAnalysis
    summary: str
    source_info: Dict[str, str]
    metadata: Dict[str, str]

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "title": "Article Title",
                "category": "AI Development",
                "analysis": {
                    "relevance_score": 0.85,
                    "category": "AI Development",
                    "impact_level": "High",
                    "key_points": ["Point 1", "Point 2"],
                    "industry_impact": "Major impact",
                    "future_implications": "Future implications"
                },
                "summary": "Detailed summary",
                "source_info": {"url": "https://example.com", "date": "2024-03-25"},
                "metadata": {"author": "John Doe", "publisher": "Tech News"}
            }]
        }
    } 