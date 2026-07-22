"""Command-line interface for the pipeline.

Usage::

    edp run --config configs/pipeline.example.yaml
    edp validate --config configs/pipeline.example.yaml
    edp plugins
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from pipeline import __version__
from pipeline.connectors import reader_registry, writer_registry
from pipeline.core.config import load_config
from pipeline.core.exceptions import PipelineError
from pipeline.core.orchestrator import Pipeline
from pipeline.transforms import transform_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edp",
        description="Enterprise Data Processing Pipeline — a config-driven ETL runner.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a pipeline from a config file.")
    run.add_argument("-c", "--config", required=True, help="Path to the YAML config.")
    run.add_argument("--json", action="store_true", help="Print the run summary as JSON.")

    validate = sub.add_parser("validate", help="Validate a config file without running.")
    validate.add_argument("-c", "--config", required=True, help="Path to the YAML config.")

    sub.add_parser("plugins", help="List available connectors and transforms.")
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = Pipeline(config).run()
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(_format_summary(result))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(f"OK: configuration '{config.name}' v{config.version} is valid.")
    print(f"  source={config.source.type}  sink={config.sink.type}")
    print(f"  transforms={[t.type for t in config.transforms]}")
    print(f"  validation.on_error={config.validation.on_error}")
    return 0


def _cmd_plugins(_: argparse.Namespace) -> int:
    print("Readers:    " + ", ".join(reader_registry.available()))
    print("Writers:    " + ", ".join(writer_registry.available()))
    print("Transforms: " + ", ".join(transform_registry.available()))
    return 0


def _format_summary(result) -> str:  # noqa: ANN001 - RunResult
    lines = [
        f"Run {result.run_id} - pipeline '{result.pipeline}'",
        f"  rows in:       {result.rows_in}",
        f"  rows valid:    {result.rows_valid}",
        f"  rows rejected: {result.rows_rejected}",
        f"  rows written:  {result.rows_out}",
        f"  duration:      {result.duration_seconds}s",
    ]
    if result.quarantine_path:
        lines.append(f"  quarantine:    {result.quarantine_path}")
    return "\n".join(lines)


_COMMANDS = {
    "run": _cmd_run,
    "validate": _cmd_validate,
    "plugins": _cmd_plugins,
}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except PipelineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
