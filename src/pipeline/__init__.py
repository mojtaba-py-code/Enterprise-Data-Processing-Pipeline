"""Enterprise Data Processing Pipeline.

A config-driven, plugin-based ETL pipeline: ingest -> validate ->
transform -> load, with structured logging, metrics and error handling.
"""
from __future__ import annotations

from pipeline.core.config import PipelineConfig, load_config
from pipeline.core.orchestrator import Pipeline, RunResult

__version__ = "1.0.0"

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "RunResult",
    "load_config",
    "__version__",
]
