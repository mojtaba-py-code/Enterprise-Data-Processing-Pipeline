from __future__ import annotations

import pandas as pd
import pytest

from pipeline.connectors import memory_connector
from pipeline.core.config import parse_config
from pipeline.core.exceptions import ValidationFailedError
from pipeline.core.orchestrator import Pipeline


def _config(on_error="quarantine", transforms=None):
    return parse_config(
        {
            "name": "e2e",
            "source": {"type": "memory", "options": {"key": "in"}},
            "sink": {"type": "memory", "options": {"key": "out"}},
            "validation": {
                "on_error": on_error,
                "schema": [
                    {"name": "id", "type": "int", "required": True, "unique": True},
                    {"name": "email", "type": "str", "required": True,
                     "pattern": r"^[^@]+@[^@]+\.[^@]+$"},
                    {"name": "age", "type": "int", "min": 0, "max": 120},
                ],
            },
            "transforms": transforms or [],
        }
    )


def test_end_to_end_quarantine(customers):
    memory_connector.set_store("in", customers)
    result = Pipeline(_config(on_error="quarantine")).run()

    # customers fixture: 5 rows, invalid = dup id(3,3), age 200x2, bad email(zz country too)
    assert result.rows_in == 5
    assert result.rows_valid == result.rows_out
    assert result.rows_rejected == result.rows_in - result.rows_valid
    assert result.rows_valid >= 1
    out = memory_connector.get_store("out")
    assert len(out) == result.rows_out


def test_end_to_end_with_transforms(customers):
    memory_connector.set_store("in", customers)
    transforms = [
        {"type": "rename", "options": {"columns": {"full_name": "name"}}},
        {"type": "split_column",
         "options": {"source": "email", "delimiter": "@", "index": 1, "target": "domain"}},
        {"type": "select", "options": {"columns": ["id", "name", "domain"]}},
    ]
    Pipeline(_config(transforms=transforms)).run()
    out = memory_connector.get_store("out")
    assert list(out.columns) == ["id", "name", "domain"]
    assert (out["domain"] == "example.com").all()


def test_fail_policy_raises(customers):
    memory_connector.set_store("in", customers)
    with pytest.raises(ValidationFailedError) as exc:
        Pipeline(_config(on_error="fail")).run()
    assert exc.value.total == 5


def test_run_result_report_is_populated(customers):
    memory_connector.set_store("in", customers)
    result = Pipeline(_config()).run()
    assert result.quality_report["total"] == 5
    assert "errors_by_rule" in result.quality_report
    assert result.duration_seconds >= 0


def test_no_schema_passes_everything():
    memory_connector.set_store("in", pd.DataFrame({"a": [1, 2, 3]}))
    cfg = parse_config(
        {
            "name": "noschema",
            "source": {"type": "memory", "options": {"key": "in"}},
            "sink": {"type": "memory", "options": {"key": "out"}},
        }
    )
    result = Pipeline(cfg).run()
    assert result.rows_out == 3
    assert result.rows_rejected == 0
