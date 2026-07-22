# Enterprise Data Processing Pipeline

A **config-driven, plugin-based** ETL pipeline in Python. Describe an entire
data flow — ingest → validate → transform → load — in a single YAML file, and
run it from the command line. Adding a new source, sink, or transformation
never requires touching the core.

[![CI](https://github.com/mojtaba-py-code/Enterprise-Data-Processing-Pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/mojtaba-py-code/Enterprise-Data-Processing-Pipeline/actions/workflows/ci.yml)

---

## Highlights

- 🧩 **Config-driven** — the whole pipeline lives in one validated YAML document.
- 🔌 **Plugin architecture** — connectors and transforms self-register; extend without forking the core.
- ✅ **Schema validation + data-quality report** — per-row, per-rule diagnostics with a machine-readable summary.
- 🛟 **Error policies** — `fail`, `drop`, or `quarantine` invalid rows to a separate file.
- 🔒 **Safe by design** — declarative transforms only; a config file can never execute arbitrary code.
- 📈 **Structured logging** — human-friendly text or JSON for log aggregators.
- 🧪 **Fully tested & typed** — 48 tests, `ruff`-clean, `mypy`-clean.
- 🐳 **Docker + CI** — reproducible runs and a GitHub Actions matrix (3.11 / 3.12).

---

## Architecture

```
                ┌──────────┐   ┌────────────┐   ┌──────────────┐   ┌────────┐
   source  ───▶ │  Ingest  │─▶ │  Validate  │─▶ │ Transform(s) │─▶ │  Load  │ ───▶ sink
  (config)      └──────────┘   └─────┬──────┘   └──────────────┘   └────────┘
                                     │ rejected rows
                                     ▼
                               ┌──────────────┐
                               │  Quarantine  │  (CSV with an _errors column)
                               └──────────────┘

        Orchestrator threads a run-scoped Context (run id, metrics, logger)
        through every stage. Connectors & transforms are resolved by name
        from pluggable registries.
```

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Config | `core/config.py` | Typed pydantic models + YAML loader (fail-fast validation) |
| Registry | `core/registry.py` | Name → class plugin lookup |
| Connectors | `connectors/` | `csv`, `json`, `memory` readers/writers |
| Validation | `validation/` | Vectorised schema checks + quality report |
| Transforms | `transforms/` | 11 declarative, safe transformations |
| Orchestrator | `core/orchestrator.py` | Runs the stages, handles quarantine, returns a summary |
| Observability | `observability/` | Structured text/JSON logging |
| CLI | `cli.py` | `run`, `validate`, `plugins` |

---

## Install

```bash
pip install -e ".[dev]"
```

Requires Python ≥ 3.11. Runtime deps: `pandas`, `pydantic`, `PyYAML`.

---

## Usage

```bash
# List available connectors and transforms
edp plugins

# Validate a config without running it
edp validate --config configs/pipeline.example.yaml

# Run the pipeline (human summary; add --json for machine output)
edp run --config configs/pipeline.example.yaml
```

Equivalent module form (no install needed): `PYTHONPATH=src python -m pipeline run -c configs/pipeline.example.yaml`.

The bundled example ingests `data/sample/customers.csv` (10 rows, some invalid),
writes 6 clean rows to `data/output/customers_clean.csv`, and quarantines 4 bad
rows — each tagged with the exact rule it broke — to `customers_rejected.csv`.

### Embedding in code

```python
from pipeline import Pipeline, load_config

result = Pipeline(load_config("configs/pipeline.example.yaml")).run()
print(result.rows_valid, result.rows_rejected, result.quality_report)
```

---

## Configuration reference

```yaml
name: customers-etl          # required
version: "1.0"

source:                      # any registered reader
  type: csv                  # csv | json | memory
  options: { path: data/sample/customers.csv }

validation:
  on_error: quarantine       # fail | drop | quarantine
  quarantine_path: data/output/customers_rejected.csv   # optional; auto-derived if omitted
  schema:
    - name: id
      type: int              # int | float | str | bool | datetime
      required: true
      unique: true
    - name: email
      required: true
      pattern: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"
    - name: age
      type: int
      min: 0
      max: 120
    - name: country
      allowed: [uk, us, fi, nl]

transforms:                  # applied in order to the valid rows
  - type: str_case
    options: { columns: [email], mode: lower }
  - type: rename
    options: { columns: { full_name: name } }
  - type: split_column
    options: { source: email, delimiter: "@", index: 1, target: email_domain }

sink:
  type: csv
  options: { path: data/output/customers_clean.csv }

observability:
  log_level: INFO            # DEBUG | INFO | WARNING | ERROR | CRITICAL
  log_format: text           # text | json
```

### Built-in transforms

| Transform | Purpose | Key options |
|-----------|---------|-------------|
| `rename` | Rename columns | `columns: {old: new}` |
| `select` | Keep/reorder columns | `columns: [..]` |
| `drop` | Drop columns | `columns: [..]` |
| `drop_nulls` | Drop rows with nulls | `columns: [..]` (optional) |
| `fillna` | Fill nulls | `values: {col: value}` |
| `cast` | Change dtypes | `columns: {col: int\|float\|str\|bool\|datetime}` |
| `dedupe` | Drop duplicate rows | `subset: [..]`, `keep` |
| `filter` | Keep matching rows | `column`, `op`, `value` |
| `split_column` | Split a string into a new column | `source`, `delimiter`, `index`, `target` |
| `str_case` | lower/upper/title/strip | `columns`, `mode` |
| `add_column` | Add a constant column | `name`, `value` |

### Validation rules

`required`, `unique`, `type` (with int-integrality & datetime parsing),
`pattern` (regex), `min` / `max` (numeric bounds), `allowed` (value set).
Each failing row is tagged with codes like `email:pattern` or `age:below_min`.

---

## Extending

Register a new connector or transform anywhere on the import path:

```python
from pipeline.transforms.base import Transform, transform_registry

@transform_registry.register("uppercase_all")
class UppercaseAll(Transform):
    def apply(self, df, context):
        return df.apply(lambda s: s.str.upper() if s.dtype == "object" else s)
```

Then reference `type: uppercase_all` in your config. No core changes required.

---

## Development

```bash
ruff check src tests     # lint
mypy src                 # type-check
pytest -q                # test (add --cov=pipeline for coverage)
```

### Docker

```bash
docker build -t edp .
docker run --rm -v "$PWD/data:/app/data" edp
```

---

## Project layout

```
src/pipeline/
├── connectors/      # readers & writers (csv, json, memory)
├── validation/      # schema validation + quality report
├── transforms/      # declarative transformations
├── observability/   # structured logging
├── core/            # config, context, registry, orchestrator
└── cli.py           # command-line entry point
configs/             # example pipeline YAML
data/sample/         # sample input data
tests/               # 48 unit + integration tests
```

## License

MIT — see [LICENSE](LICENSE).
