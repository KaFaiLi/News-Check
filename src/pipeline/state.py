"""Graph state TypedDict and reducers.

Each node receives the current state, runs its work, and returns a partial
update. LangGraph merges the partial dict into the running state.
"""

from __future__ import annotations

from typing import TypedDict

from src.anti_blocking import SessionLogger
from src.config import Settings
from src.extraction import BrowserPool
from src.models import Article, DegradationStatus, ScoredArticle


class PipelineState(TypedDict, total=False):
    settings: Settings
    pool: BrowserPool                  # shared across discover + fetch_select
    logger: SessionLogger              # shared across the whole run
    candidates: list[Article]            # post-discovery
    scored: list[ScoredArticle]          # post-ranking, full sorted pool
    selected: list[ScoredArticle]        # post-streaming-extraction (top_n)
    analyzed: list[ScoredArticle]        # post-LLM analysis
    overall_summary: str                 # cross-article synthesis
    degradation: DegradationStatus
    artifacts: dict[str, str]
