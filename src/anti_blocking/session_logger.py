"""JSON-Lines session logger for retry/anti-blocking events.

Writes one event per line to `Output/retry_logs/<session_id>_retry_log.jsonl`.
Append-only: each `log_event` appends a single line, so the file is safe
to read while a run is in flight and doesn't grow O(N²) in disk traffic
the way a "rewrite the whole array" implementation would.

The logger is thread-safe: the `BrowserPool`'s worker threads and the
LLM `ThreadPoolExecutor` may all log concurrently. A single lock guards
the underlying append.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionLogger:
    def __init__(self, output_dir: Path, session_id: str | None = None) -> None:
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        self.log_dir = Path(output_dir) / "retry_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{self.session_id}_retry_log.jsonl"
        self._lock = threading.Lock()
        # Touch the file so consumers see it even before the first event.
        self.log_path.touch()

    def log_event(self, event_type: str, **fields: Any) -> None:
        event = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "event": event_type,
            **fields,
        }
        line = json.dumps(event, default=str) + "\n"
        with self._lock, self.log_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def log_retry(
        self,
        url: str,
        attempt: int,
        max_attempts: int,
        block_type: str,
        wait_seconds: float,
        rotated_user_agent: bool,
    ) -> None:
        self.log_event(
            "retry",
            url=url,
            attempt=attempt,
            max_attempts=max_attempts,
            block_type=block_type,
            wait_seconds=wait_seconds,
            rotated_user_agent=rotated_user_agent,
        )

    def log_failure(self, url: str, reason: str) -> None:
        self.log_event("failure", url=url, reason=reason)

    def log_success(self, url: str, attempts: int) -> None:
        self.log_event("success", url=url, attempts=attempts)

    def log_degradation(self, reason: str, success_rate: float) -> None:
        self.log_event("degradation", reason=reason, success_rate=success_rate)
