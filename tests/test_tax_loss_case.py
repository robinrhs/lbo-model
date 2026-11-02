"""A second hand-calculated deal in which year 1 has a tax loss.

Same entry as tests/test_hand_case.py (equity 57, senior debt 50), but with
expensive debt (24% interest), no mandatory amortisation and higher D&A
(10% of revenue), so interest exceeds EBIT in year 1. Taxes are floored at
zero and losses are NOT carried forward (see debt.py).

Year 1: revenue 110, EBITDA 22, D&A 11, EBIT 11
    interest = 24% x 50 = 12.0;  pre-tax income = 11 - 12 = -1.0
    taxes = max(0, -1.0 x 25%) = 0
    tax shield = unlevered taxes 25% x 11 = 2.75 minus levered taxes 0 = 2.75
                 (less than 25% x 12 = 3.0: the shield is capped by the loss)
    capex 5% x 110 = 5.5, dNWC 10% x 10 = 1.0
    FCF before debt service = 22 - 0 - 5.5 - 1.0 = 15.5
    levered FCF = 15.5 - 12 = 3.5;  mandatory 0
    excess cash = 5 + 3.5 - 5 = 3.5 (100% swept)
    debt = 50 - 3.5 = 46.5;  cash = 5

Year 2: revenue 121, EBITDA 24.2, D&A 12.1, EBIT 12.1
    interest = 24% x 46.5 = 11.16;  pre-tax income = 0.94
    taxes = 25% x 0.94 = 0.235 (the year-1 loss does not reduce them)
    tax shield = 25% x 12.1 - 0.235 = 2.79 (= 25% x 11.16)
    capex 6.05, dNWC 1.1
    FCF before debt service = 24.2 - 0.235 - 6.05 - 1.1 = 16.815
    levered FCF = 16.815 - 11.16 = 5.655 (100% swept)
    debt = 46.5 - 5.655 = 40.845;  cash = 5

Exit: EV = 24.2 x 5.5 = 133.1;  equity = 133.1 - 40.845 + 5 = 97.255
    MOIC = 97.255 / 57 = 1.70623;  IRR = sqrt(MOIC) - 1 = 30.62%
"""

from __future__ import annotations

import pytest

from lbo.config import parse_config
from lbo.deal import run_deal


@pytest.fixture
def tax_loss_deal(tiny_deal_dict):
    tiny_deal_dict["operations"]["da_pct_revenue"] = 0.10
    tranche = tiny_deal_dict["debt"]["tranches"][0]
    tranche["interest_rate"] = 0.24
    tranche["mandatory_amortization_pct"] = 0.0
    return run_deal(parse_config(tiny_deal_dict))


def test_year_one_has_a_tax_loss(tax_loss_deal):
    y1 = tax_loss_deal.schedule[0]
    assert y1.ebit == pytest.approx(11.0)
    assert y1.interest == pytest.approx(12.0)
    assert y1.pre_tax_income == pytest.approx(-1.0)
    assert y1.cash_taxes == 0.0
    assert y1.interest_tax_shield == pytest.approx(2.75)
    assert y1.fcf_before_debt_service == pytest.approx(15.5)
    assert y1.levered_fcf == pytest.approx(3.5)
    assert y1.sweep_repayment == pytest.approx(3.5)
    assert y1.ending_debt == pytest.approx(46.5)
    assert y1.ending_cash == pytest.approx(5.0)


def test_year_two_pays_tax_without_loss_carryforward(tax_loss_deal):
    y2 = tax_loss_deal.schedule[1]
    assert y2.interest == pytest.approx(11.16)
    assert y2.pre_tax_income == pytest.approx(0.94)
    assert y2.cash_taxes == pytest.approx(0.235)
    assert y2.interest_tax_shield == pytest.approx(2.79)
    assert y2.levered_fcf == pytest.approx(5.655)
    assert y2.ending_debt == pytest.approx(40.845)
    assert y2.ending_cash == pytest.approx(5.0)


def test_returns_after_a_tax_loss_year(tax_loss_deal):
    r = tax_loss_deal.returns
    assert r.entry_equity == pytest.approx(57.0)
    assert r.exit_ev == pytest.approx(133.1)
    assert r.exit_equity == pytest.approx(97.255)
    assert r.moic == pytest.approx(97.255 / 57)
    assert r.irr == pytest.approx((97.255 / 57) ** 0.5 - 1, abs=1e-9)
    b = tax_loss_deal.bridge
    assert b.sum_of_components == pytest.approx(97.255 - 57, abs=1e-9)
