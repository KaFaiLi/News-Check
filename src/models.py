"""Pydantic data contracts shared across the pipeline.

The shape consumed by `document_generator.py` is:

    {"article": {"title", "source", "published_time", "url", ...},
     "analysis": {"insights": list[str] | str}}

`ScoredArticle.to_renderable()` produces that shape exactly so the existing
document generator does not need to learn about our richer models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Topic(StrEnum):
    AI = "ai"
    AI_BANKING = "ai_banking"
    AI_AGENTS = "ai_agents"
    OTHER = "other"


class SourceTier(int, Enum):
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class Article(BaseModel):
    """A discovered news article with its fetched content."""

    url: HttpUrl
    title: str
    source: str
    published_time: datetime | None = None
    snippet: str = ""

    raw_html: str | None = Field(default=None, exclude=True, repr=False)
    markdown: str | None = Field(default=None, exclude=True, repr=False)

    discovered_via_topic: Topic = Topic.OTHER
    discovered_via_query: str = ""
    appeared_in_topics: set[Topic] = Field(default_factory=set)

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, v: Any) -> str:
        return str(v).strip() if v else "Unknown Source"

    @property
    def domain(self) -> str:
        host = urlparse(str(self.url)).hostname or ""
        return host.lower().removeprefix("www.")


class ArticleAnalysis(BaseModel):
    """LLM-produced insights for one article."""

    insights: list[str] = Field(default_factory=list)


class ScoredArticle(BaseModel):
    """An article with its computed scores and final analysis."""

    article: Article
    topic_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    cross_source_consensus: float = Field(default=0.0, ge=0.0, le=1.0)
    source_tier: SourceTier = SourceTier.TIER_3
    source_tier_multiplier: float = 1.0
    recency: float = Field(default=0.0, ge=0.0, le=1.0)
    final_score: float = 0.0
    analysis: ArticleAnalysis | None = None

    def to_renderable(self) -> dict[str, Any]:
        """Shape consumed by `DocumentGenerator`."""
        pub = (
            self.article.published_time.isoformat()
            if self.article.published_time
            else "Unknown Time"
        )
        insights = self.analysis.insights if self.analysis else []
        return {
            "article": {
                "title": self.article.title,
                "source": self.article.source,
                "published_time": pub,
                "url": str(self.article.url),
                "snippet": self.article.snippet,
            },
            "analysis": {
                "insights": insights,
                "scores": {
                    "topic_relevance": self.topic_relevance,
                    "cross_source_consensus": self.cross_source_consensus,
                    "source_tier_multiplier": self.source_tier_multiplier,
                    "recency": self.recency,
                },
                "overall_score": self.final_score,
            },
        }


class DegradationStatus(BaseModel):
    """Aggregated health signal surfaced into output artifacts.

    Field names match what `document_generator.py` reads off the object
    (`is_degraded`, `success_rate`, `failed_attempts`, `total_attempts`,
    `collected_results_count`, `warnings`).
    """

    is_degraded: bool = False
    total_attempts: int = 0
    failed_attempts: int = 0
    collected_results_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 1.0
        return 1.0 - (self.failed_attempts / self.total_attempts)

    def record_attempt(self, success: bool) -> None:
        self.total_attempts += 1
        if success:
            self.consecutive_failures = 0
        else:
            self.failed_attempts += 1
            self.consecutive_failures += 1

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class MonthlyDigest(BaseModel):
    """Final pipeline output passed to the document generator."""

    month_label: str
    top_articles: list[ScoredArticle]
    overall_summary: str = ""
    degradation: DegradationStatus = Field(default_factory=DegradationStatus)

    def renderable_top_articles(self) -> list[dict[str, Any]]:
        return [a.to_renderable() for a in self.top_articles]
