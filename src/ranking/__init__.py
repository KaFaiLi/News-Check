"""Article scoring.

Selection no longer happens here — it is interleaved with parallel
extraction in `src.extraction.parallel_fetcher.fetch_and_select`, so
that failed extractions can be backfilled by the next-ranked candidate
without any pre-buffered "top-N+spare" pool.
"""

from src.ranking.scorer import score_articles

__all__ = ["score_articles"]
