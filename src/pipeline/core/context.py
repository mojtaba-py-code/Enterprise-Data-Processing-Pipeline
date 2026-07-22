"""Per-run execution context shared across all pipeline stages."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PipelineContext:
    """Carries run-scoped state (id, timing, metrics, logger) through stages.

    A single context instance is threaded through ingestion, validation and
    every transform so they can emit metrics and log against the same run id.
    """

    run_id: str
    pipeline_name: str
    started_at: datetime
    logger: logging.Logger
    metrics: dict[str, object] = field(default_factory=dict)

    def emit(self, key: str, value: object) -> None:
        """Record a single metric value."""
        self.metrics[key] = value

    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a numeric counter metric (creating it at 0 if absent)."""
        current = self.metrics.get(key, 0)
        if not isinstance(current, int):
            raise TypeError(f"Metric '{key}' is not an int counter.")
        self.metrics[key] = current + amount

    def bind(self, **fields: object) -> logging.LoggerAdapter:
        """Return a logger adapter that stamps ``run_id`` and extra fields."""
        base: dict[str, object] = {"run_id": self.run_id, "pipeline": self.pipeline_name}
        base.update(fields)
        return logging.LoggerAdapter(self.logger, base)
