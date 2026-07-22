"""Typed, validated pipeline configuration.

The entire pipeline is described by a single YAML (or dict) document that is
parsed into these pydantic models. Invalid configuration fails fast with a
clear message *before* any data is touched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pipeline.core.exceptions import ConfigError

FieldType = Literal["int", "float", "str", "bool", "datetime"]
ErrorPolicy = Literal["fail", "drop", "quarantine"]


class StageConfig(BaseModel):
    """A pluggable stage identified by ``type`` plus free-form ``options``."""

    model_config = ConfigDict(extra="forbid")

    type: str
    options: dict[str, Any] = Field(default_factory=dict)


class FieldSchema(BaseModel):
    """Validation rules for a single column."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: FieldType = "str"
    required: bool = False
    unique: bool = False
    pattern: str | None = None
    min: float | None = None
    max: float | None = None
    allowed: list[Any] | None = None

    @field_validator("name")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field name must not be empty")
        return value


class ValidationConfig(BaseModel):
    """Schema plus the policy applied to rows that fail it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: list[FieldSchema] = Field(default_factory=list, alias="schema")
    on_error: ErrorPolicy = "quarantine"
    quarantine_path: str | None = None


class ObservabilityConfig(BaseModel):
    """Logging configuration for a run."""

    model_config = ConfigDict(extra="forbid")

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    @field_validator("log_level")
    @classmethod
    def _known_level(cls, value: str) -> str:
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in levels:
            raise ValueError(f"log_level must be one of {sorted(levels)}")
        return upper


class PipelineConfig(BaseModel):
    """Top-level configuration for one pipeline run."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str = "1.0"
    source: StageConfig
    sink: StageConfig
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    transforms: list[StageConfig] = Field(default_factory=list)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)


def load_config(path: str | Path) -> PipelineConfig:
    """Load and validate a pipeline configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough of parser msg
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    return parse_config(raw, source=str(config_path))


def parse_config(raw: Any, *, source: str = "<dict>") -> PipelineConfig:
    """Validate an already-loaded mapping into a :class:`PipelineConfig`."""
    if not isinstance(raw, dict):
        raise ConfigError(f"Config in {source} must be a mapping, got {type(raw).__name__}.")
    # Support an optional top-level "pipeline:" wrapper for readability.
    data = raw.get("pipeline", raw) if "pipeline" in raw and "source" not in raw else raw
    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in {source}:\n{exc}") from exc
