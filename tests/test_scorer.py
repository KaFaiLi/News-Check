from __future__ import annotations

from datetime import date, datetime

from src.models import SourceTier, Topic
from src.ranking.scorer import (
    cross_source_consensus,
    recency_score,
    score_articles,
    topic_relevance,
)
from tests.conftest import make_article

TOPIC_QUERIES = {
    Topic.AI: ("artificial intelligence", "machine learning"),
    Topic.AI_BANKING: ("AI banking", "AI in finance"),
    Topic.AI_AGENTS: ("AI agents", "agentic AI"),
}


def test_topic_relevance_matches_strong_when_query_overlaps_title():
    art = make_article(
        url="http://x.com/a", title="Major artificial intelligence breakthrough at OpenAI",
    )
    score = topic_relevance(art, TOPIC_QUERIES)
    assert score > 0.5


def test_topic_relevance_low_when_unrelated():
    art = make_article(url="http://x.com/a", title="Local restaurant review of Italian food")
    score = topic_relevance(art, TOPIC_QUERIES)
    assert score < 0.5


def test_cross_source_consensus_counts_distinct_domains():
    base = make_article(url="http://a.com/1", title="OpenAI launches new model")
    same_story_b = make_article(url="http://b.com/1", title="OpenAI launches a new model")
    same_story_c = make_article(url="http://c.com/1", title="OpenAI launches new model today")
    same_domain_dup = make_article(
        url="http://a.com/2", title="OpenAI launches a new model now"
    )
    unrelated = make_article(url="http://d.com/1", title="Cooking tips for fall")

    pool = [base, same_story_b, same_story_c, same_domain_dup, unrelated]
    score = cross_source_consensus(base, pool)
    # base counts b and c (different domains), but NOT a.com again, NOT d.com (unrelated)
    assert score == 2 / 5.0


def test_cross_source_consensus_self_is_zero():
    art = make_article(url="http://a.com/1", title="Lonely article")
    assert cross_source_consensus(art, [art]) == 0.0


def test_recency_within_window_is_proportional():
    df = date(2026, 4, 1)
    dt = date(2026, 4, 30)
    mid = make_article(
        url="http://a.com/1", title="X", published=datetime(2026, 4, 15)
    )
    s = recency_score(mid, df, dt)
    assert 0.4 < s < 0.55


def test_recency_before_window_is_zero():
    df = date(2026, 4, 1)
    dt = date(2026, 4, 30)
    early = make_article(
        url="http://a.com/1", title="X", published=datetime(2026, 3, 15)
    )
    assert recency_score(early, df, dt) == 0.0


def test_recency_no_published_time_is_neutral_05():
    df = date(2026, 4, 1)
    dt = date(2026, 4, 30)
    art = make_article(url="http://a.com/1", title="X")
    assert recency_score(art, df, dt) == 0.5


def test_score_articles_orders_descending(scoring_settings, source_settings):
    df = date(2026, 4, 1)
    dt = date(2026, 4, 30)
    arts = [
        make_article(
            url="http://ft.com/1",
            title="AI banking deal of the decade",
            source="FT",
            topics=(Topic.AI_BANKING,),
            published=datetime(2026, 4, 28),
        ),
        make_article(
            url="http://blog.example/1",
            title="Cookie recipe",
            source="Blog",
            topics=(Topic.OTHER,),
            published=datetime(2026, 4, 5),
        ),
    ]
    scored = score_articles(
        arts,
        topic_queries=TOPIC_QUERIES,
        scoring=scoring_settings,
        sources=source_settings,
        date_from=df,
        date_to=dt,
    )
    assert scored[0].article.title.startswith("AI banking")
    assert scored[0].source_tier == SourceTier.TIER_1
    assert scored[0].final_score > scored[1].final_score
