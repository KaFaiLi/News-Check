"""Rotating User-Agent pool. Real recent Edge/Chrome on Windows + macOS."""

from __future__ import annotations

import random
from dataclasses import dataclass

_DEFAULT_POOL: tuple[str, ...] = (
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Edge on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
)


@dataclass
class UserAgentPool:
    """Random-pick UA pool with rotation tracking."""

    agents: tuple[str, ...] = _DEFAULT_POOL
    _current: str = ""
    _used_count: int = 0

    def __post_init__(self) -> None:
        if not self.agents:
            self.agents = _DEFAULT_POOL
        if not self._current:
            self._current = random.choice(self.agents)

    @property
    def current(self) -> str:
        return self._current

    def rotate(self) -> str:
        """Pick a different UA from the pool. Returns the new current UA."""
        if len(self.agents) == 1:
            return self._current
        choices = [ua for ua in self.agents if ua != self._current]
        self._current = random.choice(choices)
        self._used_count += 1
        return self._current

    def random(self) -> str:
        return random.choice(self.agents)
