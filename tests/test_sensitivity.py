from __future__ import annotations

import pytest

from lbo.config import parse_config
from lbo.deal import run_deal
from lbo.model import run_model
from lbo.sensitivity import build_sensitivity, multiple_grid


def test_grid_is_centred():
    assert multiple_grid(10.0, 0.5, 2) == [9.0, 9.5, 10.0, 10.5, 11.0]


def test_centre_cell_equals_base_case(example_config):
    table = build_sensitivity(example_config)
    centre = example_config.sensitivity.steps
    base = run_deal(example_config).returns
    assert table.irr[centre][centre] == pytest.approx(base.irr, abs=1e-12)
    assert table.moic[centre][centre] == pytest.approx(base.moic, abs=1e-12)


def test_irr_monotonic_in_multiples(example_config):
    irr = run_model(example_config).sensitivity.irr
    for row in irr:  # higher exit multiple -> higher IRR
        assert row == sorted(row)
    for col in zip(*irr, strict=True):  # higher entry multiple -> lower IRR
        assert list(col) == sorted(col, reverse=True)


def test_invalid_cells_are_none(tiny_deal_dict, tiny_config):
    # Entry at 2.0x would make 2.5x of debt exceed the purchase price.
    tiny_deal_dict["sensitivity"] = {"entry_multiple_step": 1.5, "steps": 2}
    table = build_sensitivity(parse_config(tiny_deal_dict))
    assert table.entry_multiples[0] == pytest.approx(2.0)
    assert all(cell is None for cell in table.irr[0])
    assert table.irr[2][2] == pytest.approx(run_deal(tiny_config).returns.irr)


def test_wiped_out_cells_show_total_loss_not_none(example_config):
    # Exit multiples of 1.0x-3.0x: the 1.0x column wipes out the equity.
    case = example_config.with_multiples(example_config.entry.entry_multiple, 2.0)
    table = build_sensitivity(case)
    assert table.exit_multiples[0] == pytest.approx(1.0)
    for row_irr, row_moic in zip(table.irr, table.moic, strict=True):
        assert row_irr[0] == -1.0
        assert row_moic[0] == 0.0


def test_extreme_cells_are_solved_not_fatal(tiny_deal_dict):
    # One-year tiny deal at exit 1.7x (see test_returns.py): net debt at exit is
    # 37.375 and exit EBITDA 22 in every cell, because entry/exit multiples do
    # not change the debt schedule. Equity invested = 20 x entry x 1.02 + 5 - 50.
    # Exit 1.7x leaves equity of 0.025, so every cell in that column has an IRR
    # below -99%; the solver used to give up there and stop the whole run.
    tiny_deal_dict["exit"] = {"holding_period_years": 1, "exit_multiple": 1.7}
    table = build_sensitivity(parse_config(tiny_deal_dict))
    assert table.exit_multiples == pytest.approx([0.7, 1.2, 1.7, 2.2, 2.7])
    for entry_multiple, row_irr, row_moic in zip(
        table.entry_multiples, table.irr, table.moic, strict=True
    ):
        equity = 20 * entry_multiple * 1.02 + 5 - 50
        for exit_multiple, cell_irr, cell_moic in zip(
            table.exit_multiples, row_irr, row_moic, strict=True
        ):
            exit_equity = max(0.0, 22 * exit_multiple - 37.375)
            assert cell_moic == pytest.approx(exit_equity / equity, abs=1e-9)
            assert cell_irr == pytest.approx(exit_equity / equity - 1, abs=1e-9)
    assert table.irr[2][2] == pytest.approx(0.025 / 57 - 1, abs=1e-9)


def test_unsolvable_irr_empties_only_that_cell(example_config, monkeypatch):
    # Force the solver to fail for the highest exit multiple only (largest exit
    # equity); the other cells must still be computed.
    import lbo.returns

    real_irr = lbo.returns.irr
    top_case = example_config.with_multiples(10.0, 11.0)
    threshold = run_deal(top_case).returns.exit_equity

    def flaky_irr(flows):
        if flows[-1] >= threshold - 1e-9:
            raise lbo.returns.IRRError("IRR outside the solver range")
        return real_irr(flows)

    monkeypatch.setattr(lbo.returns, "irr", flaky_irr)
    table = build_sensitivity(example_config)
    assert all(row[-1] is None for row in table.irr)
    assert all(row[-1] is None for row in table.moic)
    assert all(cell is not None for row in table.irr for cell in row[:-1])
