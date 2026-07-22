"""File-based connectors: CSV and JSON readers and writers."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.connectors.base import Reader, Writer, reader_registry, writer_registry
from pipeline.core.exceptions import ConnectorError


def _require_path(options: dict[str, object], kind: str) -> Path:
    path = options.get("path")
    if not isinstance(path, str) or not path:
        raise ConnectorError(f"{kind} connector requires a non-empty 'path' option.")
    return Path(path)


@reader_registry.register("csv")
class CsvReader(Reader):
    """Read a CSV file into a DataFrame."""

    def read(self) -> pd.DataFrame:
        path = _require_path(self.options, "csv")
        if not path.is_file():
            raise ConnectorError(f"CSV source not found: {path}")
        read_kwargs = {k: v for k, v in self.options.items() if k != "path"}
        try:
            return pd.read_csv(path, **read_kwargs)
        except Exception as exc:  # noqa: BLE001 - normalise to ConnectorError
            raise ConnectorError(f"Failed to read CSV {path}: {exc}") from exc


@writer_registry.register("csv")
class CsvWriter(Writer):
    """Write a DataFrame to a CSV file (creating parent dirs)."""

    def write(self, df: pd.DataFrame) -> None:
        path = _require_path(self.options, "csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        index = bool(self.options.get("index", False))
        try:
            df.to_csv(path, index=index)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"Failed to write CSV {path}: {exc}") from exc


@reader_registry.register("json")
class JsonReader(Reader):
    """Read a JSON file (records or lines) into a DataFrame."""

    def read(self) -> pd.DataFrame:
        path = _require_path(self.options, "json")
        if not path.is_file():
            raise ConnectorError(f"JSON source not found: {path}")
        lines = bool(self.options.get("lines", False))
        try:
            return pd.read_json(path, lines=lines)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"Failed to read JSON {path}: {exc}") from exc


@writer_registry.register("json")
class JsonWriter(Writer):
    """Write a DataFrame to a JSON file."""

    def write(self, df: pd.DataFrame) -> None:
        path = _require_path(self.options, "json")
        path.parent.mkdir(parents=True, exist_ok=True)
        orient = str(self.options.get("orient", "records"))
        lines = bool(self.options.get("lines", False))
        indent = self.options.get("indent", 2 if not lines else None)
        try:
            df.to_json(path, orient=orient, lines=lines, indent=indent)
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"Failed to write JSON {path}: {exc}") from exc
