"""Configuration loader for News-Check.

Reads `config.toml` (run-time tunables) and `.env` (secrets) into a frozen
`Settings` object that the rest of the pipeline imports.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.toml"
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class AzureOpenAISettings:
    api_key: str
    endpoint: str
    deployment: str
    api_version: str


@dataclass(frozen=True)
class RunSettings:
    date_from: date
    date_to: date
    candidates_per_topic: int

    @property
    def month_label(self) -> str:
        return self.date_from.strftime("%B %Y")


@dataclass(frozen=True)
class TopicSettings:
    ai: tuple[str, ...]
    ai_banking: tuple[str, ...]
    ai_agents: tuple[str, ...]

    def as_dict(self) -> dict[str, tuple[str, ...]]:
        return {"ai": self.ai, "ai_banking": self.ai_banking, "ai_agents": self.ai_agents}


@dataclass(frozen=True)
class SelectionSettings:
    top_n: int
    ai_banking_minimum_floor: int
    max_articles_per_source: int


@dataclass(frozen=True)
class ScoringSettings:
    weight_topic_relevance: float
    weight_cross_source_consensus: float
    weight_source_tier: float
    weight_recency: float


@dataclass(frozen=True)
class SourceSettings:
    tier_1: tuple[str, ...]
    tier_2: tuple[str, ...]
    tier_1_multiplier: float
    tier_2_multiplier: float
    tier_3_multiplier: float


@dataclass(frozen=True)
class AntiBlockingSettings:
    max_retry_attempts: int
    initial_backoff_delay: int
    max_backoff_delay: int
    random_delay_range: tuple[float, float]
    max_consecutive_failures: int


@dataclass(frozen=True)
class OutputSettings:
    output_dir: Path
    company_name: str
    include_degradation_warning: bool
    max_markdown_length: int


@dataclass(frozen=True)
class LLMSettings:
    temperature: float
    max_article_chars: int


@dataclass(frozen=True)
class ParallelismSettings:
    discovery_workers: int
    extraction_workers: int
    analysis_workers: int


@dataclass(frozen=True)
class Settings:
    azure: AzureOpenAISettings
    run: RunSettings
    topics: TopicSettings
    selection: SelectionSettings
    scoring: ScoringSettings
    sources: SourceSettings
    anti_blocking: AntiBlockingSettings
    output: OutputSettings
    llm: LLMSettings
    parallelism: ParallelismSettings
    project_root: Path = field(default=PROJECT_ROOT)


def _previous_month_window(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    last_month = today.replace(day=1) - relativedelta(days=1)
    start = last_month.replace(day=1)
    return start, last_month


def _load_run(raw: dict, today: date | None = None) -> RunSettings:
    section = raw.get("run", {})
    df_raw = section.get("date_from")
    dt_raw = section.get("date_to")

    if df_raw and dt_raw:
        date_from = date.fromisoformat(str(df_raw))
        date_to = date.fromisoformat(str(dt_raw))
    else:
        date_from, date_to = _previous_month_window(today)

    if date_from > date_to:
        raise ValueError(f"date_from ({date_from}) is after date_to ({date_to})")

    return RunSettings(
        date_from=date_from,
        date_to=date_to,
        candidates_per_topic=int(section.get("candidates_per_topic", 50)),
    )


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def load_settings(today: date | None = None) -> Settings:
    """Load Settings from config.toml + .env. Pure (modulo env vars/files)."""

    if ENV_PATH.exists():
        # Prefer the repo-local .env over inherited shell variables so the
        # pipeline uses the credentials configured for this workspace.
        load_dotenv(ENV_PATH, override=True)

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.toml not found at {CONFIG_PATH}")

    with CONFIG_PATH.open("rb") as f:
        raw = tomllib.load(f)

    azure = AzureOpenAISettings(
        api_key=_require_env("AZURE_OPENAI_API_KEY"),
        endpoint=_require_env("AZURE_OPENAI_ENDPOINT"),
        deployment=_require_env("AZURE_OPENAI_DEPLOYMENT"),
        api_version=_require_env("AZURE_OPENAI_API_VERSION"),
    )

    run = _load_run(raw, today=today)

    topics_raw = raw.get("topics", {})
    topics = TopicSettings(
        ai=tuple(topics_raw.get("ai", [])),
        ai_banking=tuple(topics_raw.get("ai_banking", [])),
        ai_agents=tuple(topics_raw.get("ai_agents", [])),
    )

    sel_raw = raw.get("selection", {})
    selection = SelectionSettings(
        top_n=int(sel_raw.get("top_n", 10)),
        ai_banking_minimum_floor=int(sel_raw.get("ai_banking_minimum_floor", 3)),
        max_articles_per_source=int(sel_raw.get("max_articles_per_source", 3)),
    )

    sc_raw = raw.get("scoring", {})
    scoring = ScoringSettings(
        weight_topic_relevance=float(sc_raw.get("weight_topic_relevance", 0.4)),
        weight_cross_source_consensus=float(sc_raw.get("weight_cross_source_consensus", 0.3)),
        weight_source_tier=float(sc_raw.get("weight_source_tier", 0.2)),
        weight_recency=float(sc_raw.get("weight_recency", 0.1)),
    )

    src_raw = raw.get("sources", {})
    sources = SourceSettings(
        tier_1=tuple(d.lower() for d in src_raw.get("tier_1", [])),
        tier_2=tuple(d.lower() for d in src_raw.get("tier_2", [])),
        tier_1_multiplier=float(src_raw.get("tier_1_multiplier", 1.4)),
        tier_2_multiplier=float(src_raw.get("tier_2_multiplier", 1.15)),
        tier_3_multiplier=float(src_raw.get("tier_3_multiplier", 1.0)),
    )

    ab_raw = raw.get("anti_blocking", {})
    delay_pair = ab_raw.get("random_delay_range", [1, 5])
    anti_blocking = AntiBlockingSettings(
        max_retry_attempts=int(ab_raw.get("max_retry_attempts", 5)),
        initial_backoff_delay=int(ab_raw.get("initial_backoff_delay", 1)),
        max_backoff_delay=int(ab_raw.get("max_backoff_delay", 60)),
        random_delay_range=(float(delay_pair[0]), float(delay_pair[1])),
        max_consecutive_failures=int(ab_raw.get("max_consecutive_failures", 3)),
    )

    out_raw = raw.get("output", {})
    output_dir = Path(out_raw.get("output_dir", "Output"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output = OutputSettings(
        output_dir=output_dir,
        company_name=str(out_raw.get("company_name", "[Your Company Name]")),
        include_degradation_warning=bool(out_raw.get("include_degradation_warning", True)),
        max_markdown_length=int(out_raw.get("max_markdown_length", 400_000)),
    )

    llm_raw = raw.get("llm", {})
    llm = LLMSettings(
        temperature=float(llm_raw.get("temperature", 0.2)),
        max_article_chars=int(llm_raw.get("max_article_chars", 60_000)),
    )

    par_raw = raw.get("parallelism", {})
    parallelism = ParallelismSettings(
        discovery_workers=max(1, int(par_raw.get("discovery_workers", 3))),
        extraction_workers=max(1, int(par_raw.get("extraction_workers", 3))),
        analysis_workers=max(1, int(par_raw.get("analysis_workers", 5))),
    )

    return Settings(
        azure=azure,
        run=run,
        topics=topics,
        selection=selection,
        scoring=scoring,
        sources=sources,
        anti_blocking=anti_blocking,
        output=output,
        llm=llm,
        parallelism=parallelism,
    )
