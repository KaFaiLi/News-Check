"""LangGraph pipeline assembly.

Order: discover → rank → fetch_select → analyze → render.

Key design choices:
  * `rank` operates on metadata only (title, snippet, source, recency,
    cross-source consensus) — no article body needed for scoring.
  * `fetch_select` walks the ranked pool in score-desc order and extracts
    article HTML in parallel via a `BrowserPool`. On any failure the next
    candidate slides up; we stop once `top_n` successful extractions
    satisfy the AI-banking floor and per-source cap.
  * `analyze` fans LLM insight calls across a thread pool; the synthesis
    call after insights stays sequential (it summarises across articles).
  * Each node records partial failures into `degradation` rather than
    raising — the pipeline always reaches `render`.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

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
from src.pipeline.state import PipelineState
from src.ranking import score_articles


def _retry_cfg(settings: Settings) -> RetryConfig:
    ab = settings.anti_blocking
    return RetryConfig(
        max_attempts=ab.max_retry_attempts,
        initial_backoff=float(ab.initial_backoff_delay),
        max_backoff=float(ab.max_backoff_delay),
        random_delay_range=ab.random_delay_range,
    )


# ---------- nodes ----------

def discover_node(state: PipelineState) -> PipelineState:
    settings: Settings = state["settings"]
    pool: BrowserPool = state["pool"]
    logger: SessionLogger = state["logger"]
    degradation: DegradationStatus = state.get("degradation") or DegradationStatus()

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

    return {"candidates": list(by_url.values()), "degradation": degradation}


def rank_node(state: PipelineState) -> PipelineState:
    settings: Settings = state["settings"]
    candidates: list[Article] = state.get("candidates", [])
    degradation: DegradationStatus = state.get("degradation") or DegradationStatus()

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
    return {"scored": scored, "degradation": degradation}


def fetch_select_node(state: PipelineState) -> PipelineState:
    """Stream extraction over the ranked pool until top_n is filled
    (with banking floor) or the pool is exhausted."""
    settings: Settings = state["settings"]
    pool: BrowserPool = state["pool"]
    logger: SessionLogger = state["logger"]
    ranked: list[ScoredArticle] = state.get("scored", [])
    degradation: DegradationStatus = state.get("degradation") or DegradationStatus()

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

    selected, degradation = fetch_and_select(
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
    return {"selected": selected, "degradation": degradation}


def analyze_node(state: PipelineState) -> PipelineState:
    settings: Settings = state["settings"]
    selected: list[ScoredArticle] = state.get("selected", [])
    degradation: DegradationStatus = state.get("degradation") or DegradationStatus()

    if not selected:
        return {"analyzed": [], "overall_summary": "", "degradation": degradation}

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

    return {"analyzed": analyzed, "overall_summary": summary, "degradation": degradation}


def render_node(state: PipelineState) -> PipelineState:
    settings: Settings = state["settings"]
    analyzed: list[ScoredArticle] = state.get("analyzed", [])
    summary: str = state.get("overall_summary", "")
    degradation: DegradationStatus = state.get("degradation") or DegradationStatus()

    renderable = [a.to_renderable() for a in analyzed]

    generator = DocumentGenerator(
        output_dir=settings.output.output_dir,
        month_label=settings.run.month_label,
        company_name=settings.output.company_name,
        include_degradation_warning=settings.output.include_degradation_warning,
    )

    artifacts: dict[str, str] = {}
    artifacts["detailed_docx"] = generator.generate_detailed_report(
        renderable,
        degradation_status=degradation,
        precomputed_summary=summary,
    )
    artifacts["email_html"] = generator.generate_email_content(
        renderable,
        degradation_status=degradation,
    )
    artifacts["articles_xlsx"] = generator.generate_articles_xlsx(
        analyzed,
        degradation_status=degradation,
    )

    print("[render] artifacts:")
    for k, v in artifacts.items():
        print(f"   {k}: {v}")

    return {"artifacts": artifacts, "degradation": degradation}


# ---------- assembly ----------

def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("discover", discover_node)
    graph.add_node("rank", rank_node)
    graph.add_node("fetch_select", fetch_select_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("render", render_node)

    graph.add_edge(START, "discover")
    graph.add_edge("discover", "rank")
    graph.add_edge("rank", "fetch_select")
    graph.add_edge("fetch_select", "analyze")
    graph.add_edge("analyze", "render")
    graph.add_edge("render", END)

    return graph.compile()


def run_pipeline(settings: Settings) -> PipelineState:
    """Build and run the pipeline with a single shared BrowserPool and
    SessionLogger across all stages — saves browser-startup churn between
    discover and fetch_select, and keeps audit trail in one log file."""
    pipeline = build_pipeline()
    workers = max(
        settings.parallelism.discovery_workers,
        settings.parallelism.extraction_workers,
    )
    logger = SessionLogger(output_dir=settings.output.output_dir)
    with BrowserPool(workers=workers) as pool:
        initial: PipelineState = {
            "settings": settings,
            "pool": pool,
            "logger": logger,
            "degradation": DegradationStatus(),
        }
        return pipeline.invoke(initial)
