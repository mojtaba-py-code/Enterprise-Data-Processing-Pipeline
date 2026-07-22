from __future__ import annotations

import pandas as pd
import pytest

from pipeline.core.exceptions import TransformError
from pipeline.transforms import transform_registry


def apply(kind, df, context, **options):
    return transform_registry.create(kind, **options).apply(df, context)


def test_rename(context):
    df = pd.DataFrame({"a": [1]})
    out = apply("rename", df, context, columns={"a": "b"})
    assert list(out.columns) == ["b"]


def test_select_keeps_order(context):
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    out = apply("select", df, context, columns=["c", "a"])
    assert list(out.columns) == ["c", "a"]


def test_drop(context):
    df = pd.DataFrame({"a": [1], "b": [2]})
    out = apply("drop", df, context, columns=["b"])
    assert list(out.columns) == ["a"]


def test_drop_nulls_subset(context):
    df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})
    out = apply("drop_nulls", df, context, columns=["a"])
    assert len(out) == 2
    assert context.metrics["rows_dropped_nulls"] == 1


def test_cast_to_int_and_datetime(context):
    df = pd.DataFrame({"n": ["1", "2"], "d": ["2020-01-01", "2020-06-01"]})
    out = apply("cast", df, context, columns={"n": "int", "d": "datetime"})
    assert str(out["n"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(out["d"])


def test_dedupe_subset(context):
    df = pd.DataFrame({"id": [1, 1, 2], "v": [1, 9, 2]})
    out = apply("dedupe", df, context, subset=["id"])
    assert len(out) == 2
    assert context.metrics["rows_deduplicated"] == 1


def test_filter_numeric(context):
    df = pd.DataFrame({"age": [10, 20, 30]})
    out = apply("filter", df, context, column="age", op=">=", value=20)
    assert list(out["age"]) == [20, 30]


def test_filter_in(context):
    df = pd.DataFrame({"c": ["a", "b", "c"]})
    out = apply("filter", df, context, column="c", op="in", value=["a", "c"])
    assert list(out["c"]) == ["a", "c"]


def test_split_column(context):
    df = pd.DataFrame({"email": ["x@foo.com", "y@bar.org"]})
    out = apply(
        "split_column", df, context, source="email", delimiter="@", index=1, target="dom"
    )
    assert list(out["dom"]) == ["foo.com", "bar.org"]


def test_str_case_lower(context):
    df = pd.DataFrame({"e": ["ABC", "DeF"]})
    out = apply("str_case", df, context, columns=["e"], mode="lower")
    assert list(out["e"]) == ["abc", "def"]


def test_add_column(context):
    df = pd.DataFrame({"a": [1, 2]})
    out = apply("add_column", df, context, name="src", value="batch")
    assert list(out["src"]) == ["batch", "batch"]


def test_missing_column_raises(context):
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(TransformError, match="not found"):
        apply("select", df, context, columns=["zzz"])


def test_bad_options_raise(context):
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(TransformError):
        apply("rename", df, context, columns={})
    with pytest.raises(TransformError):
        apply("filter", df, context, column="a", op="~~", value=1)
