"""Built-in, safe transformations.

Every transform is declarative and side-effect free: none of them evaluate
arbitrary user code, so a config file can never execute Python. Rich behaviour
(deriving columns, filtering) is expressed through explicit, bounded options.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from pipeline.core.context import PipelineContext
from pipeline.core.exceptions import TransformError
from pipeline.transforms.base import Transform, transform_registry

_CAST_DTYPES: dict[str, str] = {
    "int": "Int64",
    "float": "float64",
    "str": "string",
    "bool": "boolean",
}


def _require_columns(df: pd.DataFrame, columns: list[str], transform: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise TransformError(
            f"{transform}: columns not found in data: {missing}. "
            f"Available: {list(df.columns)}"
        )


@transform_registry.register("rename")
class Rename(Transform):
    """Rename columns using an ``old -> new`` mapping."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        mapping = self.options.get("columns")
        if not isinstance(mapping, dict) or not mapping:
            raise TransformError("rename requires a non-empty 'columns' mapping.")
        _require_columns(df, list(mapping), "rename")
        return df.rename(columns=mapping)


@transform_registry.register("select")
class Select(Transform):
    """Keep only the listed columns, in order."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        columns = self.options.get("columns")
        if not isinstance(columns, list) or not columns:
            raise TransformError("select requires a non-empty 'columns' list.")
        _require_columns(df, columns, "select")
        return df[columns].copy()


@transform_registry.register("drop")
class Drop(Transform):
    """Drop the listed columns."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        columns = self.options.get("columns")
        if not isinstance(columns, list) or not columns:
            raise TransformError("drop requires a non-empty 'columns' list.")
        _require_columns(df, columns, "drop")
        return df.drop(columns=columns)


@transform_registry.register("drop_nulls")
class DropNulls(Transform):
    """Drop rows with nulls, optionally restricted to a subset of columns."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        subset = self.options.get("columns")
        if subset is not None:
            if not isinstance(subset, list):
                raise TransformError("drop_nulls 'columns' must be a list.")
            _require_columns(df, subset, "drop_nulls")
        before = len(df)
        result = df.dropna(subset=subset)
        context.increment("rows_dropped_nulls", before - len(result))
        return result


@transform_registry.register("fillna")
class FillNa(Transform):
    """Fill nulls per column using a ``column -> value`` mapping."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        values = self.options.get("values")
        if not isinstance(values, dict) or not values:
            raise TransformError("fillna requires a non-empty 'values' mapping.")
        _require_columns(df, list(values), "fillna")
        return df.fillna(value=values)


@transform_registry.register("cast")
class Cast(Transform):
    """Cast columns to ``int``/``float``/``str``/``bool``/``datetime``."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        columns = self.options.get("columns")
        if not isinstance(columns, dict) or not columns:
            raise TransformError("cast requires a non-empty 'columns' mapping.")
        _require_columns(df, list(columns), "cast")
        result = df.copy()
        for column, target in columns.items():
            result[column] = self._cast_series(result[column], str(target), column)
        return result

    @staticmethod
    def _cast_series(series: pd.Series, target: str, column: str) -> pd.Series:
        if target == "datetime":
            return pd.to_datetime(series, errors="coerce")
        if target in ("int", "float"):
            numeric = pd.to_numeric(series, errors="coerce")
            return numeric.astype(_CAST_DTYPES[target])
        if target in _CAST_DTYPES:
            return series.astype(_CAST_DTYPES[target])
        raise TransformError(
            f"cast: unsupported type '{target}' for column '{column}'. "
            f"Supported: {sorted([*_CAST_DTYPES, 'datetime'])}"
        )


@transform_registry.register("dedupe")
class Dedupe(Transform):
    """Drop duplicate rows, optionally keyed by a subset of columns."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        subset = self.options.get("subset")
        keep = self.options.get("keep", "first")
        if subset is not None:
            if not isinstance(subset, list):
                raise TransformError("dedupe 'subset' must be a list.")
            _require_columns(df, subset, "dedupe")
        before = len(df)
        result = df.drop_duplicates(subset=subset, keep=keep)
        context.increment("rows_deduplicated", before - len(result))
        return result


_OPS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: pd.to_numeric(s, errors="coerce") > v,
    ">=": lambda s, v: pd.to_numeric(s, errors="coerce") >= v,
    "<": lambda s, v: pd.to_numeric(s, errors="coerce") < v,
    "<=": lambda s, v: pd.to_numeric(s, errors="coerce") <= v,
    "in": lambda s, v: s.isin(v),
    "not_in": lambda s, v: ~s.isin(v),
    "contains": lambda s, v: s.astype("string").str.contains(str(v), na=False),
}


@transform_registry.register("filter")
class Filter(Transform):
    """Keep rows where ``column <op> value`` holds."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        column = self.options.get("column")
        op = self.options.get("op")
        value: Any = self.options.get("value")
        if not isinstance(column, str):
            raise TransformError("filter requires a string 'column'.")
        if op not in _OPS:
            raise TransformError(f"filter 'op' must be one of {sorted(_OPS)}.")
        _require_columns(df, [column], "filter")
        if op in ("in", "not_in") and not isinstance(value, list):
            raise TransformError(f"filter op '{op}' requires a list 'value'.")
        mask = _OPS[op](df[column], value)
        before = len(df)
        result = df[mask.fillna(False)]
        context.increment("rows_filtered_out", before - len(result))
        return result


@transform_registry.register("split_column")
class SplitColumn(Transform):
    """Split a string column by a delimiter and take one part into ``target``."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        source = self.options.get("source")
        target = self.options.get("target")
        delimiter = self.options.get("delimiter", " ")
        index = self.options.get("index", 0)
        if not isinstance(source, str) or not isinstance(target, str):
            raise TransformError("split_column requires string 'source' and 'target'.")
        if not isinstance(index, int):
            raise TransformError("split_column 'index' must be an integer.")
        _require_columns(df, [source], "split_column")
        result = df.copy()
        parts = result[source].astype("string").str.split(str(delimiter))
        result[target] = parts.str.get(index)
        return result


@transform_registry.register("str_case")
class StrCase(Transform):
    """Apply ``lower``/``upper``/``title``/``strip`` to string columns."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        columns = self.options.get("columns")
        mode = str(self.options.get("mode", "lower"))
        if not isinstance(columns, list) or not columns:
            raise TransformError("str_case requires a non-empty 'columns' list.")
        _require_columns(df, columns, "str_case")
        funcs = {
            "lower": lambda s: s.str.lower(),
            "upper": lambda s: s.str.upper(),
            "title": lambda s: s.str.title(),
            "strip": lambda s: s.str.strip(),
        }
        if mode not in funcs:
            raise TransformError(f"str_case 'mode' must be one of {sorted(funcs)}.")
        result = df.copy()
        for column in columns:
            result[column] = funcs[mode](result[column].astype("string"))
        return result


@transform_registry.register("add_column")
class AddColumn(Transform):
    """Add a constant-valued column."""

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        name = self.options.get("name")
        if not isinstance(name, str):
            raise TransformError("add_column requires a string 'name'.")
        if "value" not in self.options:
            raise TransformError("add_column requires a 'value'.")
        result = df.copy()
        result[name] = self.options["value"]
        return result
