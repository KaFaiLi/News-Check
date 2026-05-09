"""Publisher tier lookup. Driven by the SourceSettings loaded from config.toml."""

from __future__ import annotations

from src.config import SourceSettings
from src.models import SourceTier


def classify_tier(domain: str, sources: SourceSettings) -> SourceTier:
    """Map a domain (e.g. 'ft.com') to its source-reliability tier."""
    if not domain:
        return SourceTier.TIER_3
    d = domain.lower().removeprefix("www.")

    for tier_1 in sources.tier_1:
        if d == tier_1 or d.endswith("." + tier_1):
            return SourceTier.TIER_1
    for tier_2 in sources.tier_2:
        if d == tier_2 or d.endswith("." + tier_2):
            return SourceTier.TIER_2
    return SourceTier.TIER_3


def tier_multiplier(tier: SourceTier, sources: SourceSettings) -> float:
    return {
        SourceTier.TIER_1: sources.tier_1_multiplier,
        SourceTier.TIER_2: sources.tier_2_multiplier,
        SourceTier.TIER_3: sources.tier_3_multiplier,
    }[tier]
