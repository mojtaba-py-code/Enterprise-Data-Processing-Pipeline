"""In-memory connectors, useful for tests and embedding the pipeline in code."""
from __future__ import annotations

import pandas as pd

from pipeline.connectors.base import Reader, Writer, reader_registry, writer_registry
from pipeline.core.exceptions import ConnectorError

# Shared stores keyed by name so a reader and writer can share a buffer.
_STORES: dict[str, pd.DataFrame] = {}


def set_store(key: str, df: pd.DataFrame) -> None:
    """Seed an in-memory store that a ``memory`` reader can later read."""
    _STORES[key] = df.copy()


def get_store(key: str) -> pd.DataFrame:
    """Return a copy of a store written by a ``memory`` writer."""
    if key not in _STORES:
        raise KeyError(f"No in-memory store named '{key}'.")
    return _STORES[key].copy()


def clear_stores() -> None:
    """Remove all in-memory stores (call between tests)."""
    _STORES.clear()


@reader_registry.register("memory")
class MemoryReader(Reader):
    """Read a DataFrame previously placed with :func:`set_store`."""

    def read(self) -> pd.DataFrame:
        key = self.options.get("key")
        if not isinstance(key, str):
            raise ConnectorError("memory reader requires a string 'key' option.")
        if key not in _STORES:
            raise ConnectorError(f"No in-memory store named '{key}'.")
        return _STORES[key].copy()


@writer_registry.register("memory")
class MemoryWriter(Writer):
    """Write a DataFrame into an in-memory store retrievable via :func:`get_store`."""

    def write(self, df: pd.DataFrame) -> None:
        key = self.options.get("key")
        if not isinstance(key, str):
            raise ConnectorError("memory writer requires a string 'key' option.")
        _STORES[key] = df.copy()
