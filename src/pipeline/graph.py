"""Pipeline orchestration: discover → rank → fetch_select → analyze → render.

The pipeline is a linear sequence of functions; each phase reads the
output of the previous one and contributes a fragment to the final
return dict. Failures inside a phase are recorded into `degradation`
rather than raised, so a partial run still reaches `render`.
"""

from __future__ import annotations

from src.analysis import (
    build_chat_model,
    generate_insights_parallel,
    synthesise_monthly_digest,
)
from src.anti_blocking import RetryConfig, SessionLogger
from src.config import Settings
from src.discovery import GoogleNewsDiscoverer
from src.document_generator import DocumentGenerator
from src.extraction import BrowserPool, fetch_and_select
from src.extraction.markdown import ensure_cache_dir
from src.models import Article, DegradationStatus, ScoredArticle, Topic
from src.ranking import score_articles


def _retry_cfg(settings: Settings) -> RetryConfig:
    ab = settings.anti_blocking
    return RetryConfig(
        max_attempts=ab.max_retry_attempts,
        initial_backoff=float(ab.initial_backoff_delay),
        max_backoff=float(ab.max_backoff_delay),
        random_delay_range=ab.random_delay_range,
    )


def discover(
    settings: Settings,
    pool: BrowserPool,
    logger: SessionLogger,
    degradation: DegradationStatus,
) -> list[Article]:
    print(f"[discover] window: {settings.run.date_from} → {settings.run.date_to}")
    print(f"[discover] using shared pool ({pool.size} workers)")

    by_url: dict[str, Article] = {}
    discoverer = GoogleNewsDiscoverer(
        pool=pool,
        candidates_per_topic=settings.run.candidates_per_topic,
        logger=logger,
    )
    for topic_name, queries in settings.topics.as_dict().items():
        if not queries:
            continue
        topic = Topic(topic_name)
        try:
            articles = discoverer.discover(
                topic=topic,
                queries=list(queries),
                date_from=settings.run.date_from,
                date_to=settings.run.date_to,
            )
        except Exception as exc:  # noqa: BLE001
            degradation.record_attempt(success=False)
            degradation.add_warning(f"Discovery failed for topic '{topic_name}': {exc}")
            logger.log_failure(url=f"<discovery:{topic_name}>", reason=str(exc)[:200])
            continue

        degradation.record_attempt(success=True)
        for art in articles:
            key = str(art.url)
            existing = by_url.get(key)
            if existing is not None:
                existing.appeared_in_topics |= art.appeared_in_topics
            else:
                by_url[key] = art
        print(f"[discover] {topic_name}: +{len(articles)} (total {len(by_url)})")

    return list(by_url.values())


def rank(settings: Settings, candidates: list[Article]) -> list[ScoredArticle]:
    topic_queries = {
        Topic.AI: settings.topics.ai,
        Topic.AI_BANKING: settings.topics.ai_banking,
        Topic.AI_AGENTS: settings.topics.ai_agents,
    }
    scored = score_articles(
        candidates,
        topic_queries=topic_queries,
        scoring=settings.scoring,
        sources=settings.sources,
        date_from=settings.run.date_from,
        date_to=settings.run.date_to,
    )
    print(f"[rank] {len(candidates)} candidates → {len(scored)} scored (full sorted pool)")
    return scored


def fetch_select(
    settings: Settings,
    ranked: list[ScoredArticle],
    pool: BrowserPool,
    logger: SessionLogger,
    degradation: DegradationStatus,
) -> list[ScoredArticle]:
    """Stream extraction over the ranked pool until top_n is filled (with
    banking floor) or the pool is exhausted."""
    cache_dir = ensure_cache_dir(settings.output.output_dir / "article_content")
    print(
        f"[fetch_select] streaming over {len(ranked)} candidates with "
        f"{pool.size} workers, target top_n={settings.selection.top_n} "
        f"(≥{settings.selection.ai_banking_minimum_floor} banking)"
    )

    def progress(submitted: int, succeeded: int, failed: int) -> None:
        if (submitted + failed) % 5 == 0 or succeeded >= settings.selection.top_n:
            print(
                f"[fetch_select] submitted={submitted} succeeded={succeeded} "
                f"failed={failed}"
            )

    selected, _ = fetch_and_select(
        ranked,
        selection=settings.selection,
        pool=pool,
        cache_dir=cache_dir,
        max_markdown_length=settings.output.max_markdown_length,
        retry_cfg=_retry_cfg(settings),
        logger=logger,
        degradation=degradation,
        on_progress=progress,
    )

    if (
        degradation.consecutive_failures >= settings.anti_blocking.max_consecutive_failures
        and not degradation.is_degraded
    ):
        degradation.is_degraded = True
        degradation.add_warning(
            f"Switched to degraded mode after {degradation.consecutive_failures} "
            f"consecutive extraction failures."
        )
        logger.log_degradation(
            reason="consecutive failures",
            success_rate=degradation.success_rate,
        )

    print(
        f"[fetch_select] final selection: {len(selected)} articles "
        f"(success_rate={degradation.success_rate:.1%})"
    )
    return selected


def analyze(
    settings: Settings,
    selected: list[ScoredArticle],
    degradation: DegradationStatus,
) -> tuple[list[ScoredArticle], str]:
    if not selected:
        return [], ""

    llm = build_chat_model(settings.azure, settings.llm)

    def progress(done: int, total: int) -> None:
        print(f"[analyze] insights {done}/{total}")

    analyzed = generate_insights_parallel(
        llm,
        selected,
        max_article_chars=settings.llm.max_article_chars,
        workers=settings.parallelism.analysis_workers,
        degradation=degradation,
        on_progress=progress,
    )

    try:
        summary = synthesise_monthly_digest(
            llm, analyzed, month_label=settings.run.month_label
        )
    except Exception as exc:  # noqa: BLE001
        degradation.add_warning(f"Synthesis failed: {exc}")
        summary = ""

    return analyzed, summary


def render(
    settings: Settings,
    analyzed: list[ScoredArticle],
    summary: str,
    degradation: DegradationStatus,
) -> dict[str, str]:
    renderable = [a.to_renderable() for a in analyzed]
    generator = DocumentGenerator(
        output_dir=settings.output.output_dir,
        month_label=settings.run.month_label,
        company_name=settings.output.company_name,
        include_degradation_warning=settings.output.include_degradation_warning,
    )
    artifacts: dict[str, str] = {
        "detailed_docx": generator.generate_detailed_report(
            renderable,
            degradation_status=degradation,
            precomputed_summary=summary,
        ),
        "email_html": generator.generate_email_content(
            renderable,
            degradation_status=degradation,
        ),
        "articles_xlsx": generator.generate_articles_xlsx(
            analyzed,
            degradation_status=degradation,
        ),
    }
    print("[render] artifacts:")
    for k, v in artifacts.items():
        print(f"   {k}: {v}")
    return artifacts


def run_pipeline(settings: Settings) -> dict[str, object]:
    """Run the full pipeline end-to-end with a single shared BrowserPool and
    SessionLogger across all stages — saves browser-startup churn between
    discover and fetch_select, and keeps the audit trail in one log file."""
    workers = max(
        settings.parallelism.discovery_workers,
        settings.parallelism.extraction_workers,
    )
    logger = SessionLogger(output_dir=settings.output.output_dir)
    degradation = DegradationStatus()

    with BrowserPool(workers=workers) as pool:
        candidates = discover(settings, pool, logger, degradation)
        scored = rank(settings, candidates)
        selected = fetch_select(settings, scored, pool, logger, degradation)

    analyzed, summary = analyze(settings, selected, degradation)
    artifacts = render(settings, analyzed, summary, degradation)

    return {
        "settings": settings,
        "candidates": candidates,
        "scored": scored,
        "selected": selected,
        "analyzed": analyzed,
        "overall_summary": summary,
        "degradation": degradation,
        "artifacts": artifacts,
    }
