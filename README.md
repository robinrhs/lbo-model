# lbo-model

A transparent leveraged buyout (LBO) model in Python. **Work in progress:** the model is being added step by step through pull requests. This README describes only what exists on this branch; the full documentation (method, example output, limitations) arrives with the documentation pull request.

## Status

What exists on this branch:

- project skeleton: a [uv](https://docs.astral.sh/uv/) project (`pyproject.toml`, `uv.lock`, Python 3.11+), the package `lbo` with its version number, MIT license
- CI on GitHub Actions for Python 3.11 and 3.12: ruff lint, ruff format check, pytest
- deal assumptions in one YAML file (`config/example.yaml`, a fictional company), validated with pydantic
- the core LBO engine (`src/lbo/`): sources & uses, operating projection, cash flow waterfall and debt schedule with cash sweep, exit returns (IRR, MOIC), value creation bridge, entry x exit multiple sensitivity
- formatted Excel export (`src/lbo/excel.py`, openpyxl): seven sheets (Assumptions, Sources & Uses, Projection, Debt Schedule, Returns, Bridge, Sensitivity) with computed values, inputs in blue, negatives in brackets
- pytest suite: a two-year deal calculated by hand, config validation, model invariants, workbook structure and formats

There is no command line interface on this branch yet. The engine and the export can be used from Python:

```python
from lbo.config import load_config
from lbo.model import run_model

result = run_model(load_config("config/example.yaml"))
print(result.base.returns.moic, result.base.returns.irr)

from lbo.excel import export_workbook

export_workbook(result, "output/lbo_example.xlsx")
```

Planned, in integration order:

- [ ] command line interface (`python -m lbo run config/example.yaml`)
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
