"""Transform plugins.

Importing this package registers every built-in transform. Custom transforms
register themselves the same way against ``transform_registry``.
"""
from __future__ import annotations

from pipeline.transforms import builtin  # noqa: F401
from pipeline.transforms.base import Transform, transform_registry

__all__ = ["Transform", "transform_registry"]
