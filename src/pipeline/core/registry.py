"""A tiny, type-safe plugin registry.

Connectors and transforms register themselves against a named registry via a
decorator, and the orchestrator instantiates them by name from config. This is
what makes the pipeline *config-driven*: adding a new capability never requires
touching the core.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from pipeline.core.exceptions import RegistryError

T = TypeVar("T")


class Registry(Generic[T]):
    """Maps a lowercase string key to a class of type ``T``."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """Decorator that registers a class under ``name``."""
        key = name.lower()

        def decorator(cls: type[T]) -> type[T]:
            if key in self._items:
                raise RegistryError(
                    f"{self._kind} '{name}' is already registered "
                    f"(by {self._items[key].__name__})."
                )
            self._items[key] = cls
            return cls

        return decorator

    def create(self, name: str, /, **kwargs: object) -> T:
        """Instantiate the class registered under ``name``."""
        cls = self.get(name)
        return cls(**kwargs)

    def get(self, name: str) -> type[T]:
        """Return the class registered under ``name``."""
        key = name.lower()
        if key not in self._items:
            raise RegistryError(
                f"Unknown {self._kind} '{name}'. "
                f"Available: {', '.join(self.available()) or '(none)'}."
            )
        return self._items[key]

    def available(self) -> list[str]:
        """Return the sorted list of registered names."""
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.lower() in self._items
