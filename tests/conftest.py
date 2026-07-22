"""Shared pytest fixtures."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from pipeline.connectors import memory_connector
from pipeline.core.context import PipelineContext
from pipeline.observability.logging import setup_logging


@pytest.fixture(autouse=True)
def _clean_memory_stores():
    """Ensure in-memory connector state never leaks between tests."""
    memory_connector.clear_stores()
    yield
    memory_connector.clear_stores()


@pytest.fixture
def context() -> PipelineContext:
    """A ready-to-use pipeline context for exercising transforms/validation."""
    return PipelineContext(
        run_id="testrun",
        pipeline_name="test",
        started_at=datetime.now(UTC),
        logger=setup_logging("WARNING", "text"),
    )


@pytest.fixture
def customers() -> pd.DataFrame:
    """A small customers frame with a mix of valid and invalid rows."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 3, 5],
            "full_name": ["Ada", "Alan", "Grace", "Grace", "Radia"],
            "email": [
                "ada@example.com",
                "alan@example.com",
                "grace@example.com",
                "grace@example.com",
                "bad-email",
            ],
            "age": [36, 41, 200, 200, 30],
            "country": ["uk", "uk", "us", "us", "zz"],
        }
    )
