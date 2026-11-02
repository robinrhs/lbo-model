"""Exit valuation and sponsor returns (IRR and MOIC).

Exit EV          = final-year EBITDA x exit multiple
Net debt at exit = remaining debt - cash on balance sheet
Exit equity      = exit EV - net debt at exit
MOIC             = exit equity / equity invested            ("how many times my money")
IRR              = discount rate r that makes NPV of the equity cash flows zero:
                   -Equity_0 + Equity_N / (1 + r)^N = 0     ("annualised return")

MOIC ignores time; IRR does not. The same 2.0x is ~15% IRR over 5 years but
~41% over 2 years. With only an entry and an exit cash flow (no dividends),
IRR = MOIC^(1/N) - 1; the general solver below also handles interim flows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Returns:
    holding_period_years: int
    exit_ebitda: float
    exit_multiple: float
    exit_ev: float
    exit_debt: float
    exit_cash: float
    exit_equity: float
    entry_equity: float
    equity_cash_flows: tuple[float, ...]
    moic: float
    irr: float

    @property
    def net_debt_at_exit(self) -> float:
        return self.exit_debt - self.exit_cash


def npv(rate: float, cash_flows: Sequence[float]) -> float:
    """Net present value with the first cash flow at t = 0 (not discounted)."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: Sequence[float], low: float = -0.99, high: float = 10.0) -> float:
    """Internal rate of return via bisection.

    Bisection is slower than Newton's method but easy to follow and cannot jump
    to a wrong root: it keeps halving the interval [low, high] in which the NPV
    changes sign until the interval is tiny. Requires a conventional cash flow
    pattern (money out first, money back later).
    """
    npv_low, npv_high = npv(low, cash_flows), npv(high, cash_flows)
    if npv_low * npv_high > 0:
        raise ValueError("IRR not bracketed: cash flows need at least one sign change")
    for _ in range(200):
        mid = (low + high) / 2
        npv_mid = npv(mid, cash_flows)
        if abs(npv_mid) < 1e-12 or (high - low) / 2 < 1e-12:
            return mid
        if npv_low * npv_mid < 0:
            high = mid
        else:
            low, npv_low = mid, npv_mid
    return (low + high) / 2


def moic(entry_equity: float, exit_equity: float) -> float:
    """Multiple on invested capital: total value returned / equity invested."""
    return exit_equity / entry_equity


def compute_returns(
    *,
    entry_equity: float,
    exit_ebitda: float,
    exit_multiple: float,
    exit_debt: float,
    exit_cash: float,
    holding_period_years: int,
) -> Returns:
    exit_ev = exit_ebitda * exit_multiple
    # Equity holders receive what is left after repaying all debt; cash on the
    # balance sheet (incl. the minimum cash) goes to them as well.
    exit_equity = exit_ev - (exit_debt - exit_cash)
    # Sponsor cash flows: invest at t = 0, nothing in between, exit proceeds at t = N.
    flows = [-entry_equity] + [0.0] * (holding_period_years - 1) + [exit_equity]
    return Returns(
        holding_period_years=holding_period_years,
        exit_ebitda=exit_ebitda,
        exit_multiple=exit_multiple,
        exit_ev=exit_ev,
        exit_debt=exit_debt,
        exit_cash=exit_cash,
        exit_equity=exit_equity,
        entry_equity=entry_equity,
        equity_cash_flows=tuple(flows),
        moic=moic(entry_equity, exit_equity),
        irr=irr(flows),
    )
