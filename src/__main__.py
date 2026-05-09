"""Entry point: `uv run python -m src`.

Loads config + secrets, runs the digest pipeline, prints a final
summary of generated artifacts.
"""

from __future__ import annotations

import sys
import traceback

from src.config import load_settings
from src.pipeline import run_pipeline


def main() -> int:
    try:
        settings = load_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print("=" * 70)
    print("News-Check — Monthly AI Digest")
    print(f"Window:    {settings.run.date_from} → {settings.run.date_to}")
    print(f"Top N:     {settings.selection.top_n} (≥{settings.selection.ai_banking_minimum_floor} AI-banking)")
    print(f"Output:    {settings.output.output_dir}")
    print("=" * 70)

    try:
        final_state = run_pipeline(settings)
    except Exception:  # noqa: BLE001
        print("Pipeline raised an unrecoverable error:", file=sys.stderr)
        traceback.print_exc()
        return 1

    degradation = final_state.get("degradation")
    artifacts = final_state.get("artifacts", {})

    print("=" * 70)
    print("Done.")
    if degradation and degradation.is_degraded:
        print(
            f"⚠️  Degraded run: success_rate={degradation.success_rate:.1%}, "
            f"failures={degradation.failed_attempts}/{degradation.total_attempts}"
        )
        for w in degradation.warnings[:5]:
            print(f"   • {w}")
    print("Artifacts:")
    for k, v in artifacts.items():
        print(f"   {k}: {v}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
