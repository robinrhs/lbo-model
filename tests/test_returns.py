from __future__ import annotations

import numpy_financial as npf
import pytest

from lbo.deal import run_deal
from lbo.returns import compute_returns, irr, moic, npv


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


# --- limited liability / total loss -----------------------------------------


def test_total_loss_is_floored_at_zero():
    # EV 50 against net debt 120: lenders lose 70, the sponsor loses its 100.
    r = compute_returns(
        entry_equity=100.0,
        exit_ebitda=10.0,
        exit_multiple=5.0,
        exit_debt=130.0,
        exit_cash=10.0,
        holding_period_years=5,
    )
    assert r.equity_value_before_floor == pytest.approx(-70.0)
    assert r.exit_equity == 0.0
    assert r.is_total_loss
    assert r.moic == 0.0
    assert r.irr == -1.0
    assert r.equity_cash_flows == (-100.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_partial_loss_is_not_floored():
    r = compute_returns(
        entry_equity=100.0,
        exit_ebitda=10.0,
        exit_multiple=5.0,
        exit_debt=30.0,
        exit_cash=5.0,
        holding_period_years=2,
    )
    assert r.exit_equity == pytest.approx(25.0)
    assert not r.is_total_loss
    assert r.moic == pytest.approx(0.25)
    assert r.irr == pytest.approx(0.25**0.5 - 1, abs=1e-9)


def test_wiped_out_example_deal_runs(example_config):
    # Exit at 1.0x EBITDA: EV far below net debt -> sponsor equity is wiped out.
    case = example_config.with_multiples(example_config.entry.entry_multiple, 1.0)
    result = run_deal(case)
    assert result.returns.moic == 0.0
    assert result.returns.irr == -1.0
    b = result.bridge
    assert b.limited_liability > 0
    assert b.total_gain == pytest.approx(-result.sources_uses.sponsor_equity)
    assert b.sum_of_components == pytest.approx(b.total_gain, abs=1e-9)
