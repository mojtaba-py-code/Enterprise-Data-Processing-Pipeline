"""Exception hierarchy for the pipeline.

All errors raised by the pipeline derive from :class:`PipelineError`, so
callers can catch the whole family with a single ``except`` clause.
"""
from __future__ import annotations


class PipelineError(Exception):
    """Base class for every error raised by the pipeline."""


class ConfigError(PipelineError):
    """Raised when a pipeline configuration is missing or invalid."""


class RegistryError(PipelineError):
    """Raised when an unknown plugin (connector/transform) is requested."""


class ConnectorError(PipelineError):
    """Raised when a reader/writer fails to read or write data."""


class TransformError(PipelineError):
    """Raised when a transformation cannot be applied."""


class ValidationFailedError(PipelineError):
    """Raised when validation fails and the policy is ``fail``."""

    def __init__(self, message: str, *, rejected: int, total: int) -> None:
        super().__init__(message)
        self.rejected = rejected
        self.total = total
