"""Pipeline orchestration: discover → rank → fetch_select → analyze → render."""

from src.pipeline.graph import run_pipeline

__all__ = ["run_pipeline"]
