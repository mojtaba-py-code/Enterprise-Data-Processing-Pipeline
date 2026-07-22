"""Row-level schema validation with a data-quality report.

Validation is *vectorised*: for each rule we compute a boolean mask of failing
rows and attach a human-readable reason. Rows accumulate zero or more reasons;
a row is valid iff it accumulated none. This scales far better than a Python
loop over rows while still giving per-row, per-rule diagnostics.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipeline.core.config import FieldSchema

ERROR_COLUMN = "_errors"


@dataclass
class ValidationResult:
    """Outcome of validating a DataFrame against a schema."""

    valid: pd.DataFrame
    rejected: pd.DataFrame
    report: dict[str, object]

    @property
    def has_rejections(self) -> bool:
        return not self.rejected.empty

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.rejected)


def validate(df: pd.DataFrame, schema: list[FieldSchema]) -> ValidationResult:
    """Validate ``df`` against ``schema`` and split it into valid/rejected."""
    n = len(df)
    reasons: list[list[str]] = [[] for _ in range(n)]
    rule_counts: Counter[str] = Counter()

    def add(mask: np.ndarray, code: str) -> None:
        for pos in np.nonzero(mask)[0]:
            reasons[pos].append(code)
            rule_counts[code] += 1

    for field in schema:
        col = field.name
        if col not in df.columns:
            if field.required:
                add(np.ones(n, dtype=bool), f"{col}:missing_column")
            continue
        _check_field(df[col], field, n, add)

    valid_mask = np.array([len(r) == 0 for r in reasons], dtype=bool)
    valid_df = df.loc[df.index[valid_mask]].copy()
    rejected_df = df.loc[df.index[~valid_mask]].copy()
    rejected_positions = np.nonzero(~valid_mask)[0]
    rejected_df[ERROR_COLUMN] = ["; ".join(reasons[pos]) for pos in rejected_positions]

    valid_count = int(valid_mask.sum())
    report: dict[str, object] = {
        "total": n,
        "valid": valid_count,
        "rejected": n - valid_count,
        "valid_ratio": round(valid_count / n, 4) if n else 1.0,
        "fields_checked": [f.name for f in schema],
        "errors_by_rule": dict(sorted(rule_counts.items())),
    }
    return ValidationResult(valid=valid_df, rejected=rejected_df, report=report)


def _check_field(series: pd.Series, field: FieldSchema, n: int, add) -> None:
    col = field.name
    notnull = series.notna().to_numpy()

    if field.required:
        add(~notnull, f"{col}:required")

    if field.type in ("int", "float"):
        numeric = pd.to_numeric(series, errors="coerce")
        num_np = numeric.to_numpy(dtype="float64", na_value=np.nan)
        numeric_ok = notnull & ~np.isnan(num_np)
        add(notnull & np.isnan(num_np), f"{col}:not_{field.type}")
        if field.type == "int":
            frac = np.abs(num_np - np.round(num_np))
            add(numeric_ok & (frac > 1e-9), f"{col}:not_int")
        _check_bounds(num_np, numeric_ok, field, add)
    elif field.type == "datetime":
        parsed = pd.to_datetime(series, errors="coerce")
        add(notnull & parsed.isna().to_numpy(), f"{col}:not_datetime")
    elif field.type == "bool":
        add(notnull & ~_bool_mask(series), f"{col}:not_bool")

    if field.pattern is not None:
        text = series.astype("string")
        matched = text.str.match(field.pattern).fillna(False).to_numpy()
        add(notnull & ~matched, f"{col}:pattern")

    if field.allowed is not None:
        add(notnull & ~series.isin(field.allowed).to_numpy(), f"{col}:not_allowed")

    if field.unique:
        dup = series.duplicated(keep=False).to_numpy()
        add(notnull & dup, f"{col}:duplicate")


def _check_bounds(num_np: np.ndarray, numeric_ok: np.ndarray, field: FieldSchema, add) -> None:
    with np.errstate(invalid="ignore"):
        if field.min is not None:
            add(numeric_ok & (num_np < field.min), f"{field.name}:below_min")
        if field.max is not None:
            add(numeric_ok & (num_np > field.max), f"{field.name}:above_max")


def _bool_mask(series: pd.Series) -> np.ndarray:
    truthy = {"true", "false", "0", "1", "yes", "no"}

    def ok(value: object) -> bool:
        if pd.isna(value):
            return True  # nulls are handled by the 'required' rule
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)) and value in (0, 1):
            return True
        return str(value).strip().lower() in truthy

    return series.map(ok).to_numpy(dtype=bool)
