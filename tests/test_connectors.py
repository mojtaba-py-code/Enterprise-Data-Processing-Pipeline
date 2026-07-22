from __future__ import annotations

import pandas as pd
import pytest

from pipeline.connectors import memory_connector, reader_registry, writer_registry
from pipeline.core.exceptions import ConnectorError


def test_csv_round_trip(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    out = tmp_path / "nested" / "data.csv"
    writer_registry.create("csv", path=str(out)).write(df)
    assert out.is_file()  # parent dirs created
    back = reader_registry.create("csv", path=str(out)).read()
    pd.testing.assert_frame_equal(back, df)


def test_json_round_trip(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    out = tmp_path / "data.json"
    writer_registry.create("json", path=str(out)).write(df)
    back = reader_registry.create("json", path=str(out)).read()
    pd.testing.assert_frame_equal(back.sort_index(axis=1), df.sort_index(axis=1))


def test_missing_source_raises():
    with pytest.raises(ConnectorError, match="not found"):
        reader_registry.create("csv", path="nope.csv").read()


def test_missing_path_option_raises():
    with pytest.raises(ConnectorError, match="path"):
        reader_registry.create("csv").read()


def test_memory_connector_round_trip():
    df = pd.DataFrame({"a": [1]})
    memory_connector.set_store("in", df)
    read = reader_registry.create("memory", key="in").read()
    pd.testing.assert_frame_equal(read, df)
    writer_registry.create("memory", key="out").write(df)
    pd.testing.assert_frame_equal(memory_connector.get_store("out"), df)
