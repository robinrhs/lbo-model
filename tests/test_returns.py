from __future__ import annotations

import numpy_financial as npf
import pytest

from lbo.config import parse_config
from lbo.deal import run_deal
from lbo.returns import IRRError, compute_returns, irr, moic, npv


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
    with pytest.raises(IRRError, match="sign change"):
        irr([100.0, 10.0])
    with pytest.raises(IRRError, match="sign change"):
        irr([-100.0, 0.0])


# --- IRR outside the solver's starting interval [-99%, +1000%] ----------------


@pytest.mark.parametrize(
    ("flows", "expected"),
    [
        # -100 + 0.5 / (1 + r) = 0  ->  1 + r = 0.005  ->  r = -99.5%
        ([-100.0, 0.5], -0.995),
        # -100 + 0.0001 / (1 + r)^2 = 0  ->  1 + r = 0.001  ->  r = -99.9%
        ([-100.0, 0.0, 0.0001], -0.999),
        # -1 + 16 / (1 + r) = 0  ->  1 + r = 16  ->  r = 1500%
        ([-1.0, 16.0], 15.0),
        # -1 + 144 / (1 + r)^2 = 0  ->  1 + r = 12  ->  r = 1100%
        ([-1.0, 0.0, 144.0], 11.0),
    ],
)
def test_irr_outside_starting_interval(flows, expected):
    assert irr(flows) == pytest.approx(expected, abs=1e-9)
    assert irr(flows) == pytest.approx(npf.irr(flows), abs=1e-9)


# Tiny deal (conftest.TINY_DEAL) held for one year only. Year 1 is unchanged
# from tests/test_hand_case.py: EBITDA 22, debt 42.375, cash 5, so net debt at
# exit = 37.375. Equity invested = 57.
def _one_year_tiny(tiny_deal_dict, exit_multiple):
    tiny_deal_dict["exit"] = {"holding_period_years": 1, "exit_multiple": exit_multiple}
    return parse_config(tiny_deal_dict)


def test_near_total_loss_deal_below_minus_99_percent(tiny_deal_dict):
    # Exit 1.7x: EV = 22 x 1.7 = 37.4; equity = 37.4 - 37.375 = 0.025.
    # MOIC = 0.025 / 57; one year, so IRR = MOIC - 1 = -99.956%.
    r = run_deal(_one_year_tiny(tiny_deal_dict, 1.7)).returns
    assert r.exit_equity == pytest.approx(0.025, abs=1e-9)
    assert r.moic == pytest.approx(0.025 / 57, abs=1e-12)
    assert r.irr == pytest.approx(0.025 / 57 - 1, abs=1e-9)
    assert r.irr < -0.99


def test_extreme_winner_deal_above_1000_percent(tiny_deal_dict):
    # Exit 40x: EV = 880; equity = 880 - 37.375 = 842.625.
    # MOIC = 842.625 / 57 = 14.7829; IRR = MOIC - 1 = 1378.3%.
    r = run_deal(_one_year_tiny(tiny_deal_dict, 40.0)).returns
    assert r.exit_equity == pytest.approx(842.625, abs=1e-9)
    assert r.moic == pytest.approx(842.625 / 57, abs=1e-12)
    assert r.irr == pytest.approx(842.625 / 57 - 1, abs=1e-9)
    assert r.irr > 10.0


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
