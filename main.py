"""Entry point for `uv run main.py`.

Equivalent to `uv run python -m src`. Edit `config.toml` and `.env` first,
then run.
"""

from __future__ import annotations

from src.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
