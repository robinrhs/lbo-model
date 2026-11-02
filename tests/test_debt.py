from __future__ import annotations

from itertools import pairwise

import pytest

from lbo.config import parse_config
from lbo.deal import run_deal
from lbo.debt import (
    LiquidityError,
    allocate_sweep,
    cash_taxes,
    interest_tax_shield,
    mandatory_repayment,
)


def _deleveraging_deal(tiny_deal_dict: dict) -> dict:
    """Low leverage, strong cash flow, long hold: debt is fully repaid early."""
    d = tiny_deal_dict
    d["exit"]["holding_period_years"] = 8
    d["operations"]["ebitda_margin"] = 0.35
    d["debt"]["tranches"] = [
        {
            "name": "Senior",
            "amount_x_ebitda": 1.0,
            "interest_rate": 0.08,
            "mandatory_amortization_pct": 0.25,
            "sweep": True,
        },
        {
            "name": "Second Lien",
            "amount_x_ebitda": 0.5,
            "interest_rate": 0.11,
            "mandatory_amortization_pct": 0.0,
            "sweep": True,
        },
        {
            "name": "Mezzanine",
            "amount_x_ebitda": 0.5,
            "interest_rate": 0.13,
            "mandatory_amortization_pct": 0.0,
            "sweep": False,
        },
    ]
    return d


def test_debt_never_negative_example(example_config):
    for year in run_deal(example_config).schedule:
        for tranche in year.tranches:
            assert tranche.beginning_balance >= 0
            assert tranche.ending_balance >= -1e-12


def test_debt_never_negative_when_fully_repaid(tiny_deal_dict):
    result = run_deal(parse_config(_deleveraging_deal(tiny_deal_dict)))
    for year in result.schedule:
        for tranche in year.tranches:
            assert tranche.ending_balance >= -1e-12
    final = {t.name: t.ending_balance for t in result.schedule[-1].tranches}
    assert final["Senior"] == pytest.approx(0.0, abs=1e-9)
    assert final["Second Lien"] == pytest.approx(0.0, abs=1e-9)
    # Non-sweepable mezzanine is untouched (no amortisation, no sweep).
    assert final["Mezzanine"] == pytest.approx(10.0)


def test_sweep_follows_seniority(tiny_deal_dict):
    result = run_deal(parse_config(_deleveraging_deal(tiny_deal_dict)))
    for year in result.schedule:
        senior, second, _ = year.tranches
        # The second-lien tranche only receives sweep cash once senior is gone.
        if second.sweep_repayment > 0:
            assert senior.ending_balance == pytest.approx(0.0, abs=1e-9)


def test_cash_reconciles_each_year(example_config):
    schedule = run_deal(example_config).schedule
    opening_cash = example_config.entry.minimum_cash
    for year in schedule:
        assert year.beginning_cash == pytest.approx(opening_cash)
        expected = year.beginning_cash + year.levered_fcf - year.total_repayment
        assert year.ending_cash == pytest.approx(expected, abs=1e-9)
        # The model never drops below the minimum cash balance in the example.
        assert year.ending_cash >= example_config.entry.minimum_cash - 1e-9
        opening_cash = year.ending_cash


def test_debt_balances_roll_forward(example_config):
    schedule = run_deal(example_config).schedule
    for prev, curr in pairwise(schedule):
        for p, c in zip(prev.tranches, curr.tranches, strict=True):
            assert c.beginning_balance == pytest.approx(p.ending_balance)
    for year in schedule:
        for t in year.tranches:
            assert t.ending_balance == pytest.approx(
                t.beginning_balance - t.mandatory_repayment - t.sweep_repayment
            )


def test_interest_on_beginning_balance(example_config):
    year1 = run_deal(example_config).schedule[0]
    rates = {t.name: t.interest_rate for t in example_config.debt.tranches}
    for t in year1.tranches:
        assert t.interest == pytest.approx(t.beginning_balance * rates[t.name])


def test_sweep_uses_only_configured_share(example_config):
    pct = example_config.debt.cash_sweep_pct
    for year in run_deal(example_config).schedule:
        assert year.sweep_repayment == pytest.approx(year.excess_cash * pct)


def test_taxes_and_shield():
    assert cash_taxes(ebit=100, interest=40, tax_rate=0.3) == pytest.approx(18.0)
    assert interest_tax_shield(ebit=100, interest=40, tax_rate=0.3) == pytest.approx(12.0)
    # Loss-making year: no tax, and the shield is limited to the taxes avoided.
    assert cash_taxes(ebit=10, interest=40, tax_rate=0.3) == 0.0
    assert interest_tax_shield(ebit=10, interest=40, tax_rate=0.3) == pytest.approx(3.0)


def test_mandatory_repayment_capped_at_balance():
    assert mandatory_repayment(100, 0.25, balance=60) == pytest.approx(25)
    assert mandatory_repayment(100, 0.25, balance=10) == pytest.approx(10)


def test_allocate_sweep():
    assert allocate_sweep(30, [20, 50, 50], [True, False, True]) == [20, 0, 10]
    assert allocate_sweep(-5, [20], [True]) == [0]


def test_liquidity_shortfall_raises(tiny_deal_dict):
    tiny_deal_dict["debt"]["tranches"][0]["mandatory_amortization_pct"] = 1.0
    with pytest.raises(LiquidityError, match="Year 1"):
        run_deal(parse_config(tiny_deal_dict))


def test_sweep_is_balance_based(example_config):
    # Documented convention: the sweep applies to the whole cash balance above
    # minimum cash (incl. cash retained in earlier years), not only the year's flow.
    result = run_deal(example_config)
    pct = example_config.debt.cash_sweep_pct
    minimum = example_config.entry.minimum_cash
    for y in result.schedule:
        cash_above_min = y.beginning_cash + y.levered_fcf - y.mandatory_repayment - minimum
        assert y.excess_cash == pytest.approx(max(0.0, cash_above_min))
        assert y.sweep_repayment == pytest.approx(pct * y.excess_cash)
    # From year 2 on, retained cash is swept again: more than pct x this year's flow.
    y2 = result.schedule[1]
    assert y2.sweep_repayment > pct * (y2.levered_fcf - y2.mandatory_repayment)
