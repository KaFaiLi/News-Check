"""LLM analysis: per-article insights."""

from src.analysis.insights import generate_insights
from src.analysis.llm import build_chat_model
from src.analysis.parallel_insights import generate_insights_parallel

__all__ = [
    "build_chat_model",
    "generate_insights",
    "generate_insights_parallel",
]
