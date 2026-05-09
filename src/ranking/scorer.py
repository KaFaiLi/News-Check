"""Article scoring.

Final score = w_topic·topic_relevance + w_consensus·cross_source_consensus
              + w_tier·source_tier_signal + w_recency·recency

All component scores are clipped to [0, 1]. The tier multiplier from
SourceSettings is applied after the weighted sum, which preserves the
relative ordering produced by the additive part while still letting
reputable publishers rise above otherwise-equal articles.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date

from rapidfuzz import fuzz

from src.config import ScoringSettings, SourceSettings
from src.discovery.publishers import classify_tier, tier_multiplier
from src.models import Article, ScoredArticle, Topic

# Tier signal feeds the additive part — Tier 1 = 1.0, Tier 2 = 0.6, Tier 3 = 0.3.
# This is independent from the multiplicative `source_tier_multiplier` applied
# after the weighted sum.
_TIER_SIGNAL = {1: 1.0, 2: 0.6, 3: 0.3}


def topic_relevance(article: Article, topic_queries: dict[Topic, tuple[str, ...]]) -> float:
    """Best-match similarity between the article (title + snippet) and any
    query for any topic the article appeared under. Range [0, 1]."""
    haystack = f"{article.title} {article.snippet}".strip().lower()
    if not haystack:
        return 0.0

    topics_to_check: Iterable[Topic] = article.appeared_in_topics or {article.discovered_via_topic}
    best = 0.0
    for t in topics_to_check:
        for q in topic_queries.get(t, ()):
            score = fuzz.token_set_ratio(haystack, q.lower()) / 100.0
            if score > best:
                best = score
    return min(max(best, 0.0), 1.0)


_CONSENSUS_SATURATION = 5


def cross_source_consensus(article: Article, all_articles: list[Article]) -> float:
    """How many *other* outlets covered the same story?

    We approximate "same story" by fuzzy-matching titles across articles
    from different domains, since deduplication-by-URL has already happened.
    Score saturates at 5 distinct co-covering outlets — we short-circuit
    the inner loop once that's reached, since the score can't go higher.
    """
    title = article.title.lower()
    if not title:
        return 0.0

    distinct_domains: set[str] = set()
    for other in all_articles:
        if other is article or other.domain == article.domain:
            continue
        if other.domain in distinct_domains:
            continue
        sim = fuzz.token_set_ratio(title, other.title.lower())
        if sim >= 75:
            distinct_domains.add(other.domain)
            if len(distinct_domains) >= _CONSENSUS_SATURATION:
                break
    return min(len(distinct_domains) / _CONSENSUS_SATURATION, 1.0)


def recency_score(article: Article, date_from: date, date_to: date) -> float:
    """Linear recency curve within [date_from, date_to]. 1.0 at the end of
    the window, 0.0 at the start. Articles without a published_time get
    0.5 (neutral) rather than zero so they aren't penalised for missing
    metadata that Google News didn't expose."""
    if article.published_time is None:
        return 0.5

    pub_dt = article.published_time
    if pub_dt.tzinfo is not None:
        pub_dt = pub_dt.astimezone(UTC).replace(tzinfo=None)
    pub_d = pub_dt.date()

    if pub_d < date_from:
        return 0.0
    if pub_d > date_to:
        return 1.0

    span = (date_to - date_from).days
    if span <= 0:
        return 1.0
    elapsed = (pub_d - date_from).days
    return elapsed / span


def score_articles(
    articles: list[Article],
    *,
    topic_queries: dict[Topic, tuple[str, ...]],
    scoring: ScoringSettings,
    sources: SourceSettings,
    date_from: date,
    date_to: date,
) -> list[ScoredArticle]:
    """Compute scores for every article, returning sorted-by-score list."""
    if not articles:
        return []

    # Pre-compute tier and recency for every article.
    scored: list[ScoredArticle] = []
    for art in articles:
        tier = classify_tier(art.domain, sources)
        mult = tier_multiplier(tier, sources)
        tier_sig = _TIER_SIGNAL[int(tier)]

        topic_score = topic_relevance(art, topic_queries)
        consensus = cross_source_consensus(art, articles)
        rec = recency_score(art, date_from, date_to)

        weighted = (
            scoring.weight_topic_relevance * topic_score
            + scoring.weight_cross_source_consensus * consensus
            + scoring.weight_source_tier * tier_sig
            + scoring.weight_recency * rec
        )
        final = weighted * mult

        scored.append(
            ScoredArticle(
                article=art,
                topic_relevance=topic_score,
                cross_source_consensus=consensus,
                source_tier=tier,
                source_tier_multiplier=mult,
                recency=rec,
                final_score=final,
            )
        )

    scored.sort(key=lambda s: s.final_score, reverse=True)
    return scored
