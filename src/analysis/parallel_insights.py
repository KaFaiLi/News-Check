"""Parallel LLM insight generation across the selected articles.

`AzureChatOpenAI` is thread-safe (it's an HTTP wrapper), so we fan out
per-article calls through a `ThreadPoolExecutor`. Failures attach an
empty `ArticleAnalysis` and are recorded into `degradation`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import AzureChatOpenAI

from src.analysis.insights import generate_insights
from src.models import ArticleAnalysis, DegradationStatus, ScoredArticle


def generate_insights_parallel(
    llm: AzureChatOpenAI,
    selected: list[ScoredArticle],
    *,
    max_article_chars: int,
    workers: int,
    degradation: DegradationStatus,
    on_progress: callable | None = None,
) -> list[ScoredArticle]:
    """Generate insights for every article concurrently.

    Mutates each `ScoredArticle.analysis` in place, returning the same list.
    """
    if not selected:
        return []

    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="llm") as exe:
        future_to_sa = {
            exe.submit(
                generate_insights,
                llm,
                sa.article,
                max_article_chars=max_article_chars,
            ): sa
            for sa in selected
        }
        completed = 0
        for fut in as_completed(future_to_sa):
            sa = future_to_sa[fut]
            completed += 1
            try:
                sa.analysis = fut.result()
            except Exception as exc:  # noqa: BLE001
                degradation.record_attempt(success=False)
                degradation.add_warning(
                    f"Insight generation failed for '{sa.article.title[:60]}': {exc}"
                )
                sa.analysis = ArticleAnalysis(insights=[])
            if on_progress is not None:
                on_progress(completed, len(selected))

    return selected
