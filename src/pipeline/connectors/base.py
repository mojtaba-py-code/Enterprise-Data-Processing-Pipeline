"""Connector abstractions and registries.

A :class:`Reader` ingests a ``DataFrame`` from some source; a :class:`Writer`
persists one to some sink. Both are plugins registered by name so the
orchestrator can build them straight from config.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from pipeline.core.registry import Registry


class Reader(ABC):
    """Reads a :class:`pandas.DataFrame` from a source."""

    def __init__(self, **options: object) -> None:
        self.options = options

    @abstractmethod
    def read(self) -> pd.DataFrame:
        """Return the ingested data."""


class Writer(ABC):
    """Writes a :class:`pandas.DataFrame` to a sink."""

    def __init__(self, **options: object) -> None:
        self.options = options

    @abstractmethod
    def write(self, df: pd.DataFrame) -> None:
        """Persist ``df`` to the configured sink."""


reader_registry: Registry[Reader] = Registry("reader")
writer_registry: Registry[Writer] = Registry("writer")
