from __future__ import annotations

import pandas as pd

from pipeline.core.config import FieldSchema
from pipeline.validation import validate
from pipeline.validation.validator import ERROR_COLUMN


def test_valid_rows_pass():
    df = pd.DataFrame({"id": [1, 2], "email": ["a@b.com", "c@d.com"]})
    schema = [
        FieldSchema(name="id", type="int", required=True, unique=True),
        FieldSchema(name="email", type="str", required=True, pattern=r"^[^@]+@[^@]+\.[^@]+$"),
    ]
    result = validate(df, schema)
    assert result.report["valid"] == 2
    assert result.report["rejected"] == 0
    assert result.rejected.empty


def test_required_null_is_rejected():
    df = pd.DataFrame({"email": ["a@b.com", None]})
    result = validate(df, [FieldSchema(name="email", type="str", required=True)])
    assert result.report["rejected"] == 1
    assert "email:required" in result.rejected[ERROR_COLUMN].iloc[0]


def test_pattern_failure_is_rejected():
    df = pd.DataFrame({"email": ["ok@x.com", "nope"]})
    result = validate(df, [FieldSchema(name="email", pattern=r"^[^@]+@[^@]+\.[^@]+$")])
    assert result.report["rejected"] == 1


def test_numeric_bounds():
    df = pd.DataFrame({"age": [10, -1, 200]})
    result = validate(df, [FieldSchema(name="age", type="int", min=0, max=120)])
    assert result.report["valid"] == 1
    assert result.report["errors_by_rule"]["age:below_min"] == 1
    assert result.report["errors_by_rule"]["age:above_max"] == 1


def test_type_failure():
    df = pd.DataFrame({"age": ["12", "abc", "3.5"]})
    result = validate(df, [FieldSchema(name="age", type="int")])
    # "abc" -> not_int (uncoercible); "3.5" -> not_int (fractional); "12" ok
    assert result.report["valid"] == 1
    assert result.report["rejected"] == 2


def test_unique_flags_all_duplicates():
    df = pd.DataFrame({"id": [1, 1, 2]})
    result = validate(df, [FieldSchema(name="id", type="int", unique=True)])
    assert result.report["rejected"] == 2


def test_allowed_values():
    df = pd.DataFrame({"c": ["uk", "zz"]})
    result = validate(df, [FieldSchema(name="c", allowed=["uk", "us"])])
    assert result.report["rejected"] == 1


def test_missing_required_column():
    df = pd.DataFrame({"other": [1]})
    result = validate(df, [FieldSchema(name="id", required=True)])
    assert result.report["rejected"] == 1
    assert "id:missing_column" in result.rejected[ERROR_COLUMN].iloc[0]


def test_empty_frame():
    df = pd.DataFrame({"id": pd.Series([], dtype="int64")})
    result = validate(df, [FieldSchema(name="id", type="int", required=True)])
    assert result.report["total"] == 0
    assert result.report["valid_ratio"] == 1.0


def test_multiple_reasons_on_one_row():
    df = pd.DataFrame({"id": [1, 1], "age": [5, 5]})
    schema = [
        FieldSchema(name="id", type="int", unique=True),
        FieldSchema(name="age", type="int", min=10),
    ]
    result = validate(df, schema)
    reasons = result.rejected[ERROR_COLUMN].iloc[0]
    assert "id:duplicate" in reasons and "age:below_min" in reasons
