from __future__ import annotations

import pytest
from openpyxl import load_workbook

from lbo.excel import INPUT_BLUE, export_workbook
from lbo.model import run_model

EXPECTED_SHEETS = [
    "Assumptions",
    "Sources & Uses",
    "Projection",
    "Debt Schedule",
    "Returns",
    "Bridge",
    "Sensitivity",
]


@pytest.fixture
def workbook(example_config, tmp_path):
    result = run_model(example_config)
    path = export_workbook(result, tmp_path / "out" / "lbo.xlsx")
    return result, load_workbook(path)


def _find_row(ws, label):
    for row in ws.iter_rows(min_col=1, max_col=ws.max_column):
        if row[0].value == label:
            return row
    raise AssertionError(f"label {label!r} not found on {ws.title}")


def test_one_sheet_per_schedule(workbook):
    _, wb = workbook
    assert wb.sheetnames == EXPECTED_SHEETS


def test_headers_frozen(workbook):
    _, wb = workbook
    for ws in wb:
        assert ws.freeze_panes == "B5"


def test_inputs_are_blue(workbook):
    _, wb = workbook
    row = _find_row(wb["Assumptions"], "LTM EBITDA")
    assert row[1].value == 40
    assert row[1].font.color.rgb.endswith(INPUT_BLUE)


def test_calculations_are_not_blue(workbook):
    _, wb = workbook
    row = _find_row(wb["Projection"], "Revenue")
    assert not row[2].font.color.rgb.endswith(INPUT_BLUE)


def test_returns_sheet_matches_model(workbook):
    result, wb = workbook
    irr_row = _find_row(wb["Returns"], "IRR (5-year hold)")
    assert irr_row[1].value == pytest.approx(result.base.returns.irr)
    assert irr_row[1].number_format.startswith("0.0%")


def test_sources_and_uses_totals(workbook):
    _, wb = workbook
    ws = wb["Sources & Uses"]
    assert _find_row(ws, "Total uses")[1].value == pytest.approx(
        _find_row(ws, "Total sources")[1].value
    )


def test_bridge_shares_are_na_for_a_loss(example_config, tmp_path):
    result = run_model(example_config.with_multiples(10.0, 2.0))
    wb = load_workbook(export_workbook(result, tmp_path / "loss.xlsx"))
    row = _find_row(wb["Bridge"], "Revenue growth")
    assert row[1].value > 0
    assert row[2].value == "n/a"
