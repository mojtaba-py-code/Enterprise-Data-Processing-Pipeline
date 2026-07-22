"""Connector plugins.

Importing this package registers every built-in reader and writer against the
shared registries. Third-party connectors simply need to import
``reader_registry`` / ``writer_registry`` and apply the decorator.
"""
from __future__ import annotations

from pipeline.connectors import file_connectors, memory_connector  # noqa: F401
from pipeline.connectors.base import (
    Reader,
    Writer,
    reader_registry,
    writer_registry,
)

__all__ = [
    "Reader",
    "Writer",
    "reader_registry",
    "writer_registry",
]
