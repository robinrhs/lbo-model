"""A tiny deal calculated by hand, line by line.

Entry: revenue 100, EBITDA 20, 5.0x -> EV 100; fees 2% = 2; minimum cash 5.
    Uses = 100 + 2 + 5 = 107. Senior debt 2.5x = 50. Equity = 107 - 50 = 57.

Year 1: revenue 110, EBITDA 22, D&A 5.5, EBIT 16.5
    interest = 10% x 50 = 5.0;  taxes = 25% x (16.5 - 5.0) = 2.875
    capex 5.5, dNWC = 10% x 10 = 1.0
    FCF before debt service = 22 - 2.875 - 5.5 - 1.0 = 12.625
    levered FCF = 12.625 - 5.0 = 7.625
    mandatory = 10% x 50 = 5.0;  excess cash = 5 + 7.625 - 5 - 5 = 2.625 (100% swept)
    debt = 50 - 5 - 2.625 = 42.375;  cash = 5

Year 2: revenue 121, EBITDA 24.2, D&A 6.05, EBIT 18.15
    interest = 10% x 42.375 = 4.2375;  taxes = 25% x 13.9125 = 3.478125
    capex 6.05, dNWC 1.1
    FCF before debt service = 24.2 - 3.478125 - 6.05 - 1.1 = 13.571875
    levered FCF = 13.571875 - 4.2375 = 9.334375
    mandatory 5.0;  sweep = 5 + 9.334375 - 5 - 5 = 4.334375
    debt = 42.375 - 5 - 4.334375 = 33.040625;  cash = 5

Exit: EV = 24.2 x 5.5 = 133.1;  equity = 133.1 - 33.040625 + 5 = 105.059375
    MOIC = 105.059375 / 57 = 1.84315;  IRR = sqrt(MOIC) - 1 = 35.76%

Bridge: EBITDA growth (24.2 - 20) x 5.0 = 21.0  [revenue 21 x 20% x 5 = 21.0, margin 0]
        multiple (5.5 - 5.0) x 24.2 = 12.1
        deleveraging 50 - 33.040625 = 16.959375 (cash unchanged)
        fees -2.0
        total 48.059375 = 105.059375 - 57
"""

from __future__ import annotations

import pytest

from lbo.deal import run_deal


def test_sources_and_uses(tiny_config):
    su = run_deal(tiny_config).sources_uses
    assert su.purchase_ev == pytest.approx(100.0)
    assert su.transaction_fees == pytest.approx(2.0)
    assert su.total_uses == pytest.approx(107.0)
    assert su.debt == {"Senior": pytest.approx(50.0)}
    assert su.sponsor_equity == pytest.approx(57.0)


def test_year_one(tiny_config):
    y1 = run_deal(tiny_config).schedule[0]
    assert y1.ebitda == pytest.approx(22.0)
    assert y1.interest == pytest.approx(5.0)
    assert y1.cash_taxes == pytest.approx(2.875)
    assert y1.interest_tax_shield == pytest.approx(1.25)  # 25% x 5.0
    assert y1.fcf_before_debt_service == pytest.approx(12.625)
    assert y1.levered_fcf == pytest.approx(7.625)
    assert y1.mandatory_repayment == pytest.approx(5.0)
    assert y1.sweep_repayment == pytest.approx(2.625)
    assert y1.ending_debt == pytest.approx(42.375)
    assert y1.ending_cash == pytest.approx(5.0)


def test_year_two(tiny_config):
    y2 = run_deal(tiny_config).schedule[1]
    assert y2.interest == pytest.approx(4.2375)
    assert y2.cash_taxes == pytest.approx(3.478125)
    assert y2.levered_fcf == pytest.approx(9.334375)
    assert y2.sweep_repayment == pytest.approx(4.334375)
    assert y2.ending_debt == pytest.approx(33.040625)


def test_exit_and_returns(tiny_config):
    r = run_deal(tiny_config).returns
    assert r.exit_ev == pytest.approx(133.1)
    assert r.exit_equity == pytest.approx(105.059375)
    assert r.moic == pytest.approx(105.059375 / 57)
    assert r.irr == pytest.approx((105.059375 / 57) ** 0.5 - 1, abs=1e-9)


def test_bridge(tiny_config):
    b = run_deal(tiny_config).bridge
    assert b.revenue_growth == pytest.approx(21.0)
    assert b.margin_expansion == pytest.approx(0.0, abs=1e-12)
    assert b.multiple_expansion == pytest.approx(12.1)
    assert b.debt_paydown == pytest.approx(16.959375)
    assert b.cash_generation == pytest.approx(0.0, abs=1e-12)
    assert b.transaction_fees == pytest.approx(-2.0)
    assert b.total_gain == pytest.approx(48.059375)
