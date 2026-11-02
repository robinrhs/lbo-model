# lbo-model

A transparent leveraged buyout (LBO) model in Python. **Work in progress:** the model is being added step by step through pull requests. This README describes only what exists on this branch; the full documentation (method, example output, limitations) arrives with the documentation pull request.

## Status

What exists on this branch:

- project skeleton: a [uv](https://docs.astral.sh/uv/) project (`pyproject.toml`, `uv.lock`, Python 3.11+), the package `lbo` with its version number, MIT license
- CI on GitHub Actions for Python 3.11 and 3.12: ruff lint, ruff format check, pytest, CLI smoke test
- deal assumptions in one YAML file (`config/example.yaml`, a fictional company), validated with pydantic
- the core LBO engine (`src/lbo/`): sources & uses, operating projection, cash flow waterfall and debt schedule with cash sweep, exit returns (IRR, MOIC), value creation bridge, entry x exit multiple sensitivity
- formatted Excel export (`src/lbo/excel.py`, openpyxl): seven sheets (Assumptions, Sources & Uses, Projection, Debt Schedule, Returns, Bridge, Sensitivity) with computed values, inputs in blue, negatives in brackets
- command line interface (`src/lbo/cli.py`, rich): prints sources & uses, returns, bridge and sensitivity tables and optionally writes the workbook
- pytest suite: a two-year deal calculated by hand, config validation, model invariants, workbook structure and formats, CLI runs

Run the example (fictional company, EUR millions):

```bash
uv run python -m lbo run config/example.yaml
uv run python -m lbo run config/example.yaml --excel output/lbo_example.xlsx
```

Planned, in integration order:

- [ ] full README with method, example output, example workbook and limitations
- [ ] review fixes: limited liability in wiped-out deals, bridge percentages, sweep convention, golden regression test
- [ ] input validation and IRR solver hardening

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

## License

[MIT](LICENSE) © 2026 Robin-Philip Rehschuh
