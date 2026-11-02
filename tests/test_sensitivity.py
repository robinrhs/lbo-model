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
