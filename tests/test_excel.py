from __future__ import annotations

import pytest
from openpyxl import load_workbook

from lbo.excel import INPUT_BLUE, MOIC, export_workbook
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


# --- wiped-out deal: example case exited at 1.0x EBITDA ------------------------
# Independent derivation from the golden example numbers (README): the debt
# schedule does not depend on the exit multiple, so exit EBITDA is still
# 574.262 / 10.0 = 57.4262 and net debt at exit 83.399. At 1.0x:
#   exit EV = 57.4262; EV - net debt = 57.4262 - 83.399 = -25.972
#   -> exit equity 0, lenders absorb 25.972, sponsor loses its 240.0.
WIPED_EXIT_EV = 574.262 / 10.0
WIPED_SHORTFALL = 83.399 - WIPED_EXIT_EV  # 25.972
TOL = 1e-3


@pytest.fixture
def wiped_workbook(example_config, tmp_path):
    result = run_model(example_config.with_multiples(10.0, 1.0))
    return result, load_workbook(export_workbook(result, tmp_path / "wiped.xlsx"))


def test_wiped_out_returns_column_adds_up_to_zero(wiped_workbook):
    _, wb = wiped_workbook
    ws = wb["Returns"]
    ev = _find_row(ws, "Exit enterprise value")[1].value
    debt = _find_row(ws, "Less: debt at exit")[1].value
    cash = _find_row(ws, "Plus: cash at exit")[1].value
    shortfall = _find_row(ws, "Plus: shortfall borne by lenders (limited liability)")[1].value
    equity = _find_row(ws, "Exit equity value")[1].value
    assert ev == pytest.approx(WIPED_EXIT_EV, abs=TOL)
    assert debt + cash == pytest.approx(-83.399, abs=TOL)
    assert shortfall == pytest.approx(WIPED_SHORTFALL, abs=TOL)
    assert equity == 0.0
    assert ev + debt + cash + shortfall == pytest.approx(equity, abs=1e-9)


def test_wiped_out_moic_displays_zero_not_dash(wiped_workbook):
    _, wb = wiped_workbook
    moic = _find_row(wb["Returns"], "MOIC")[1]
    assert moic.value == 0.0
    assert moic.number_format == MOIC
    zero_section = moic.number_format.split(";")[2]
    assert zero_section.startswith('0.00"x"')
    irr = _find_row(wb["Returns"], "IRR (5-year hold)")[1]
    assert irr.value == -1.0


def test_wiped_out_bridge_has_limited_liability_row(wiped_workbook):
    _, wb = wiped_workbook
    ws = wb["Bridge"]
    components = [
        "Revenue growth",
        "Margin expansion",
        "Multiple expansion",
        "Debt paydown",
        "Cash generation",
        "Transaction fees",
        "Limited liability (loss absorbed by lenders)",
    ]
    values = [_find_row(ws, label)[1].value for label in components]
    assert values[-1] == pytest.approx(WIPED_SHORTFALL, abs=TOL)
    entry = _find_row(ws, "Entry equity")[1].value
    exit_equity = _find_row(ws, "Exit equity")[1].value
    assert entry == pytest.approx(240.0)
    assert exit_equity == 0.0
    assert entry + sum(values) == pytest.approx(exit_equity, abs=1e-9)
    assert _find_row(ws, "Total equity gain")[1].value == pytest.approx(-240.0)
    assert _find_row(ws, "Total equity gain")[2].value == "n/a"


def test_wiped_out_sensitivity_moic_cells_display_zero(wiped_workbook):
    result, wb = wiped_workbook
    ws = wb["Sensitivity"]
    zero_cells = [
        cell
        for row in ws.iter_rows(min_col=2)
        for cell in row
        if cell.value == 0.0 and cell.number_format.startswith('0.00"x"')
    ]
    wiped_moic_cells = sum(row.count(0.0) for row in result.sensitivity.moic)
    assert wiped_moic_cells > 0
    assert len(zero_cells) == wiped_moic_cells
    assert all(cell.number_format == MOIC for cell in zero_cells)
