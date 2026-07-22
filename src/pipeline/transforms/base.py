"""Transform abstraction and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from pipeline.core.context import PipelineContext
from pipeline.core.registry import Registry


class Transform(ABC):
    """A pure-ish function ``DataFrame -> DataFrame`` configured by options."""

    def __init__(self, **options: object) -> None:
        self.options = options

    @abstractmethod
    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Return a new DataFrame with the transform applied."""


transform_registry: Registry[Transform] = Registry("transform")
