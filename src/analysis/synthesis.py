"""Cross-article synthesis: a single 'monthly themes' paragraph for the digest."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

from src.models import ScoredArticle

_SYSTEM_PROMPT = """You are a senior research analyst at a global investment bank,
writing the opening paragraph of a monthly AI briefing for senior banking colleagues.

Synthesize the most important themes across the supplied articles in 3-4 sentences:
  • Main findings or announcements
  • Industry impact and significance.
  • Future implications or next steps.

Do not list articles individually; weave themes. Neutral, precise tone. No hype."""

_USER_TEMPLATE = """Month: {month_label}

Articles (title — source — bullet insights):
{articles_block}

Write the 3-4 sentence opening synthesis."""


_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM_PROMPT), ("user", _USER_TEMPLATE)]
)


def _format_articles(articles: list[ScoredArticle]) -> str:
    lines: list[str] = []
    for sa in articles:
        bullets = []
        if sa.analysis and sa.analysis.insights:
            bullets = [f"    - {b}" for b in sa.analysis.insights[:3]]
        bullet_block = "\n".join(bullets) if bullets else "    - (no insights available)"
        lines.append(
            f"- {sa.article.title} — {sa.article.source}\n{bullet_block}"
        )
    return "\n".join(lines)


def synthesise_monthly_digest(
    llm: AzureChatOpenAI,
    articles: list[ScoredArticle],
    *,
    month_label: str,
) -> str:
    if not articles:
        return ""

    chain = _PROMPT | llm
    response = chain.invoke(
        {"month_label": month_label, "articles_block": _format_articles(articles)}
    )
    return str(response.content).strip()
