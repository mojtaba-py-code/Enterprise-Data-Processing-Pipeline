"""The orchestrator: build stages from config and run them in order.

Flow: ingest -> validate -> transform(s) -> load, with a quarantine branch for
rejected records and a structured summary returned to the caller.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pipeline.connectors import reader_registry, writer_registry
from pipeline.connectors.base import Writer
from pipeline.core.config import PipelineConfig, StageConfig
from pipeline.core.context import PipelineContext
from pipeline.core.exceptions import ValidationFailedError
from pipeline.observability.logging import setup_logging
from pipeline.transforms import transform_registry
from pipeline.validation import ValidationResult, validate


@dataclass
class RunResult:
    """Summary of a completed pipeline run."""

    run_id: str
    pipeline: str
    rows_in: int
    rows_valid: int
    rows_rejected: int
    rows_out: int
    duration_seconds: float
    quality_report: dict[str, object] = field(default_factory=dict)
    quarantine_path: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class Pipeline:
    """Executes a :class:`PipelineConfig` end to end."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(self) -> RunResult:
        cfg = self.config
        logger = setup_logging(cfg.observability.log_level, cfg.observability.log_format)
        context = PipelineContext(
            run_id=uuid.uuid4().hex[:12],
            pipeline_name=cfg.name,
            started_at=datetime.now(UTC),
            logger=logger,
        )
        log = context.bind(stage="orchestrator")
        log.info("Pipeline '%s' v%s started", cfg.name, cfg.version)

        df = self._ingest(context)
        rows_in = len(df)

        valid_df, rejected, report = self._validate(df, context)
        rows_valid = len(valid_df)

        validated = valid_df
        for stage in cfg.transforms:
            validated = self._apply_transform(stage, validated, context)

        self._load(validated, context)
        quarantine_path = self._quarantine(rejected, context)

        duration = (datetime.now(UTC) - context.started_at).total_seconds()
        result = RunResult(
            run_id=context.run_id,
            pipeline=cfg.name,
            rows_in=rows_in,
            rows_valid=rows_valid,
            rows_rejected=len(rejected),
            rows_out=len(validated),
            duration_seconds=round(duration, 4),
            quality_report=report,
            quarantine_path=quarantine_path,
        )
        log.info(
            "Pipeline finished: in=%d valid=%d rejected=%d out=%d in %.3fs",
            result.rows_in,
            result.rows_valid,
            result.rows_rejected,
            result.rows_out,
            result.duration_seconds,
        )
        return result

    # -- stages -----------------------------------------------------------

    def _ingest(self, context: PipelineContext) -> pd.DataFrame:
        src = self.config.source
        reader = reader_registry.create(src.type, **src.options)
        df = reader.read()
        context.emit("rows_ingested", len(df))
        context.bind(stage="ingest", connector=src.type).info("Ingested %d rows", len(df))
        return df

    def _validate(
        self, df: pd.DataFrame, context: PipelineContext
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
        vcfg = self.config.validation
        log = context.bind(stage="validate")
        if not vcfg.schema_:
            log.info("No schema configured; skipping validation")
            return df, df.iloc[0:0].copy(), {}

        result: ValidationResult = validate(df, vcfg.schema_)
        context.emit("quality_report", result.report)
        log.info(
            "Validation: valid=%d rejected=%d ratio=%s",
            result.valid_count,
            result.rejected_count,
            result.report["valid_ratio"],
        )

        if result.has_rejections and vcfg.on_error == "fail":
            raise ValidationFailedError(
                f"{result.rejected_count} of {result.total} rows failed validation.",
                rejected=result.rejected_count,
                total=result.total,
            )
        # For both 'drop' and 'quarantine' we proceed with the valid rows;
        # 'quarantine' additionally persists the rejected ones (see _quarantine).
        return result.valid, result.rejected, result.report

    def _apply_transform(
        self, stage: StageConfig, df: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        transform = transform_registry.create(stage.type, **stage.options)
        before = len(df)
        result = transform.apply(df, context)
        context.bind(stage="transform", transform=stage.type).info(
            "Applied '%s': %d -> %d rows", stage.type, before, len(result)
        )
        return result

    def _load(self, df: pd.DataFrame, context: PipelineContext) -> None:
        sink = self.config.sink
        writer: Writer = writer_registry.create(sink.type, **sink.options)
        writer.write(df)
        context.emit("rows_written", len(df))
        context.bind(stage="load", connector=sink.type).info("Wrote %d rows", len(df))

    def _quarantine(self, rejected: pd.DataFrame, context: PipelineContext) -> str | None:
        vcfg = self.config.validation
        if rejected.empty or vcfg.on_error != "quarantine":
            return None
        path = self._quarantine_path()
        if path is None:
            context.bind(stage="quarantine").warning(
                "%d rows rejected but no quarantine path could be derived", len(rejected)
            )
            return None
        writer = writer_registry.create("csv", path=str(path))
        writer.write(rejected)
        context.bind(stage="quarantine").info(
            "Quarantined %d rejected rows to %s", len(rejected), path
        )
        return str(path)

    def _quarantine_path(self) -> Path | None:
        vcfg = self.config.validation
        if vcfg.quarantine_path:
            return Path(vcfg.quarantine_path)
        sink_path = self.config.sink.options.get("path")
        if isinstance(sink_path, str) and sink_path:
            p = Path(sink_path)
            return p.with_name(f"{p.stem}_rejected.csv")
        return None
