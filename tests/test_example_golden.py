"""Golden regression test for config/example.yaml.

The README publishes these headline numbers. If a change to the engine moves
any of them, this test fails, and the README example output must be
regenerated (uv run python -m lbo run config/example.yaml) before committing.
The values were cross-checked against a separate from-scratch calculation
(textbook formulas, no import of this package) that is not part of this
repository. The hand calculations that are included live in
tests/test_hand_case.py and tests/test_tax_loss_case.py.
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from lbo.deal import run_deal
from lbo.excel import export_workbook
from lbo.model import run_model

TOL = 1e-3  # EUR millions; the README shows one decimal


def test_example_headline_returns(example_config):
    result = run_deal(example_config)
    r = result.returns
    assert result.sources_uses.sponsor_equity == pytest.approx(240.0, abs=1e-9)
    assert r.exit_ev == pytest.approx(574.262, abs=TOL)
    assert r.net_debt_at_exit == pytest.approx(83.399, abs=TOL)
    assert r.exit_equity == pytest.approx(490.863, abs=TOL)
    assert r.moic == pytest.approx(2.0453, abs=1e-4)
    assert r.irr == pytest.approx(0.15385, abs=1e-5)


def test_example_bridge_values(example_config):
    b = run_deal(example_config).bridge
    assert b.revenue_growth == pytest.approx(110.455, abs=TOL)
    assert b.margin_expansion == pytest.approx(63.807, abs=TOL)
    assert b.multiple_expansion == pytest.approx(0.0, abs=1e-9)
    assert b.debt_paydown == pytest.approx(72.499, abs=TOL)
    assert b.cash_generation == pytest.approx(14.103, abs=TOL)
    assert b.transaction_fees == pytest.approx(-10.0, abs=1e-9)
    assert b.limited_liability == 0.0
    assert b.total_gain == pytest.approx(250.863, abs=TOL)


def test_example_debt_schedule_in_workbook(example_config, tmp_path):
    result = run_model(example_config)
    ws = load_workbook(export_workbook(result, tmp_path / "golden.xlsx"))["Debt Schedule"]
    rows = {row[0].value: [c.value for c in row[1:6]] for row in ws.iter_rows(max_col=6)}

    expected_total_debt = [171.186, 159.583, 145.101, 127.604, 107.501]
    expected_ending_cash = [12.814, 15.604, 18.482, 21.497, 24.103]
    assert rows["Total debt"] == pytest.approx(expected_total_debt, abs=TOL)
    assert rows["Ending cash"] == pytest.approx(expected_ending_cash, abs=TOL)
    # The sheet must show exactly what the model computed.
    assert rows["Total debt"] == pytest.approx([y.ending_debt for y in result.base.schedule])
