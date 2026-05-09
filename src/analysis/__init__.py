"""LLM analysis: per-article insights + monthly synthesis."""

from src.analysis.insights import generate_insights
from src.analysis.llm import build_chat_model
from src.analysis.parallel_insights import generate_insights_parallel
from src.analysis.synthesis import synthesise_monthly_digest

__all__ = [
    "build_chat_model",
    "generate_insights",
    "generate_insights_parallel",
    "synthesise_monthly_digest",
]
