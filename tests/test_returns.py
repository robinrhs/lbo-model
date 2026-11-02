from __future__ import annotations

import numpy_financial as npf
import pytest

from lbo.deal import run_deal
from lbo.returns import irr, moic, npv


def test_irr_matches_numpy_financial_known_case():
    # Invest 100, receive 200 after 5 years: 2.0x -> 2^(1/5) - 1 = 14.87%.
    flows = [-100.0, 0.0, 0.0, 0.0, 0.0, 200.0]
    assert irr(flows) == pytest.approx(npf.irr(flows), abs=1e-9)
    assert irr(flows) == pytest.approx(2 ** (1 / 5) - 1, abs=1e-9)


def test_irr_matches_numpy_financial_with_interim_flows():
    flows = [-250.0, 10.0, 15.0, -5.0, 20.0, 410.0]
    assert irr(flows) == pytest.approx(npf.irr(flows), abs=1e-9)


def test_irr_matches_numpy_financial_on_example_deal(example_config):
    r = run_deal(example_config).returns
    assert r.irr == pytest.approx(npf.irr(list(r.equity_cash_flows)), abs=1e-9)


def test_npv_at_irr_is_zero():
    flows = [-100.0, 30.0, 40.0, 50.0]
    assert npv(irr(flows), flows) == pytest.approx(0.0, abs=1e-8)


def test_irr_requires_sign_change():
    with pytest.raises(ValueError):
        irr([100.0, 10.0])


def test_moic_and_exit_equity(example_config):
    r = run_deal(example_config).returns
    assert r.exit_equity == pytest.approx(r.exit_ev - r.net_debt_at_exit)
    assert r.moic == pytest.approx(moic(r.entry_equity, r.exit_equity))
    # No interim dividends -> IRR = MOIC^(1/N) - 1
    assert r.irr == pytest.approx(r.moic ** (1 / r.holding_period_years) - 1, abs=1e-9)
