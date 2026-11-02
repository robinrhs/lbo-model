"""Exit valuation and sponsor returns (IRR and MOIC).

Exit EV          = final-year EBITDA x exit multiple
Net debt at exit = remaining debt - cash on balance sheet
Exit equity      = max(0, exit EV - net debt at exit)      (limited liability)
MOIC             = exit equity / equity invested            ("how many times my money")
IRR              = discount rate r that makes NPV of the equity cash flows zero:
                   -Equity_0 + Equity_N / (1 + r)^N = 0     ("annualised return")

MOIC ignores time; IRR does not. The same 2.0x is ~15% IRR over 5 years but
~41% over 2 years. With only an entry and an exit cash flow (no dividends),
IRR = MOIC^(1/N) - 1; the general solver below also handles interim flows.

Limited liability: if the business is worth less than its net debt at exit,
the lenders take a loss and the sponsor loses its whole cheque, but never more.
Exit equity is therefore floored at zero. A total loss is reported as
MOIC 0.00x and IRR -100% (the IRR formula has no finite solution when nothing
comes back, so -100% is set by convention rather than solved).
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
    exit_equity: float  # after the zero floor (what the sponsor actually receives)
    entry_equity: float
    equity_cash_flows: tuple[float, ...]
    moic: float
    irr: float

    @property
    def net_debt_at_exit(self) -> float:
        return self.exit_debt - self.exit_cash

    @property
    def equity_value_before_floor(self) -> float:
        """Exit EV - net debt; negative when the deal is under water."""
        return self.exit_ev - self.net_debt_at_exit

    @property
    def is_total_loss(self) -> bool:
        return self.exit_equity == 0.0


def npv(rate: float, cash_flows: Sequence[float]) -> float:
    """Net present value with the first cash flow at t = 0 (not discounted)."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


class IRRError(ValueError):
    """Raised when no IRR can be found for a set of cash flows."""


# Search limits for the IRR solver. -100% itself is excluded because NPV is not
# defined there (division by zero); +1,000,000% is far beyond any real deal.
IRR_LOWEST = -1 + 1e-12
IRR_HIGHEST = 1e4


def irr(cash_flows: Sequence[float], low: float = -0.99, high: float = 10.0) -> float:
    """Internal rate of return via bisection.

    Bisection is slower than Newton's method but easy to follow and cannot jump
    to a wrong root: it keeps halving the interval [low, high] in which the NPV
    changes sign until the interval is tiny. Requires a conventional cash flow
    pattern (money out first, money back later).

    [low, high] is only the starting guess. If the NPV has the same sign at both
    ends, the interval is widened step by step (low towards -100%, high
    upwards) until it brackets the root, so a near-total loss (IRR below -99%)
    or a spectacular deal (IRR above 1000%) is still solved.
    """
    if not (any(cf < 0 for cf in cash_flows) and any(cf > 0 for cf in cash_flows)):
        raise IRRError("IRR not defined: cash flows need at least one sign change")
    npv_low, npv_high = npv(low, cash_flows), npv(high, cash_flows)
    while npv_low * npv_high > 0 and (low > IRR_LOWEST or high < IRR_HIGHEST):
        # Move each end a big step outwards: low halves its distance to -100%
        # ten times over, high doubles (both clamped to the search limits).
        low = max(IRR_LOWEST, -1 + (1 + low) / 1024)
        high = min(IRR_HIGHEST, 2 * high)
        npv_low, npv_high = npv(low, cash_flows), npv(high, cash_flows)
    if npv_low * npv_high > 0:
        raise IRRError(f"IRR outside the solver range ({IRR_LOWEST:.10%} to {IRR_HIGHEST:,.0%})")
    for _ in range(300):
        mid = (low + high) / 2
        npv_mid = npv(mid, cash_flows)
        if npv_mid == 0 or (high - low) / 2 < 1e-12:
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
    # balance sheet (incl. the minimum cash) goes to them as well. Limited
    # liability: if debt exceeds the sale proceeds, equity gets zero, not a bill.
    exit_equity = max(0.0, exit_ev - (exit_debt - exit_cash))
    # Sponsor cash flows: invest at t = 0, nothing in between, exit proceeds at t = N.
    flows = [-entry_equity] + [0.0] * (holding_period_years - 1) + [exit_equity]
    if exit_equity == 0.0:
        # Total loss: every euro invested is gone. NPV is negative at any finite
        # rate, so the solver cannot find a root; -100% is the conventional value.
        deal_moic, deal_irr = 0.0, -1.0
    else:
        deal_moic, deal_irr = moic(entry_equity, exit_equity), irr(flows)
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
        moic=deal_moic,
        irr=deal_irr,
    )
