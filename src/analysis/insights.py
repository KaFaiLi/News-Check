"""Per-article insight generation tuned for an investment-banking audience."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

from src.models import Article, ArticleAnalysis


class _InsightPayload(BaseModel):
    """Structured-output schema asked of the LLM."""

    insights: list[str] = Field(
        default_factory=list,
        description="3-5 bullet-point insights, each ≤ 35 words, focused on implications for IB.",
    )


_SYSTEM_PROMPT = """You are a senior research analyst at a global investment bank.
You read AI / financial-technology news and distill what matters for banking professionals:
deal implications, regulatory exposure, competitive positioning, infrastructure shifts, and
client-facing capabilities. You are precise, neutral, and skeptical of hype.

When given a single article, return 3-5 insight bullets (each ≤ 35 words). Lead with the
implication, not a recap. If the article is paywalled, light, or off-topic, produce
fewer bullets. Never invent facts the article does not state."""


_USER_TEMPLATE = """Article title: {title}
Source: {source}
URL: {url}

Article body (markdown, possibly truncated):
---
{body}
---

Produce the structured analysis."""


_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM_PROMPT), ("user", _USER_TEMPLATE)]
)


def generate_insights(
    llm: AzureChatOpenAI,
    article: Article,
    *,
    max_article_chars: int,
) -> ArticleAnalysis:
    """Run the per-article insight prompt and return a parsed `ArticleAnalysis`."""
    body = article.markdown or article.snippet or ""
    if len(body) > max_article_chars:
        body = body[:max_article_chars] + "\n\n[... truncated ...]"

    structured_llm = llm.with_structured_output(_InsightPayload)
    chain = _PROMPT | structured_llm

    payload: _InsightPayload = chain.invoke(
        {
            "title": article.title,
            "source": article.source,
            "url": str(article.url),
            "body": body,
        }
    )

    insights = [str(b).strip() for b in (payload.insights or []) if str(b).strip()]
    return ArticleAnalysis(insights=insights)
