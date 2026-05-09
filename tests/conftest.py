"""Test fixtures and shared helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import pytest

from src.config import (
    ScoringSettings,
    SelectionSettings,
    SourceSettings,
)
from src.models import Article, Topic


def make_article(
    *,
    url: str,
    title: str,
    source: str = "",
    snippet: str = "",
    published: datetime | None = None,
    topics: Iterable[Topic] = (Topic.AI,),
) -> Article:
    topics_set = set(topics)
    primary = next(iter(topics_set)) if topics_set else Topic.AI
    return Article(
        url=url,
        title=title,
        source=source or "Test Source",
        snippet=snippet,
        published_time=published,
        discovered_via_topic=primary,
        appeared_in_topics=topics_set,
    )


@pytest.fixture
def source_settings() -> SourceSettings:
    return SourceSettings(
        tier_1=("ft.com", "bloomberg.com", "reuters.com", "wsj.com"),
        tier_2=("techcrunch.com", "forbes.com"),
        tier_1_multiplier=1.4,
        tier_2_multiplier=1.15,
        tier_3_multiplier=1.0,
    )


@pytest.fixture
def scoring_settings() -> ScoringSettings:
    return ScoringSettings(
        weight_topic_relevance=0.4,
        weight_cross_source_consensus=0.3,
        weight_source_tier=0.2,
        weight_recency=0.1,
    )


@pytest.fixture
def selection_settings() -> SelectionSettings:
    return SelectionSettings(
        top_n=10,
        ai_banking_minimum_floor=3,
        max_articles_per_source=3,
    )
