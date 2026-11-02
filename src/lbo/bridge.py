"""Value creation bridge: where did the equity gain come from?

Starting point (all exact identities, no approximation):

    Entry equity = EV_0 + fees + Cash_0 - Debt_0
    Exit equity  = EV_N + Cash_N - Debt_N
    Gain         = Exit equity - Entry equity
                 = (EV_N - EV_0) + (NetDebt_0 - NetDebt_N) - fees

The change in EV is split in a fixed order (EBITDA first, then multiple):

    EV_N - EV_0 = (EBITDA_N - EBITDA_0) x Multiple_0      <- EBITDA growth
                + (Multiple_N - Multiple_0) x EBITDA_N    <- multiple expansion

EBITDA growth is further split (revenue first, then margin):

    EBITDA_N - EBITDA_0 = (Rev_N - Rev_0) x Margin_0      <- revenue growth
                        + Rev_N x (Margin_N - Margin_0)   <- margin expansion

    (each multiplied by Multiple_0 to express it in EV terms)

Order matters for the split (not for the total): valuing multiple expansion on
EXIT EBITDA attributes the "cross term" (more EBITDA x higher multiple) to the
multiple. Other conventions exist; this one is common in PE value creation
reporting and is documented so the numbers can be reproduced.

Deleveraging = reduction in net debt (debt repaid + cash built up), i.e. the
free cash flow that accrued to equity holders. Transaction fees are value that
leaves the deal at closing and are shown as a separate negative bar so the
components sum exactly to the total gain.

Limited liability: exit equity is floored at zero (see returns.py). In a
wiped-out deal, the identity above would give a NEGATIVE exit equity, i.e. a
loss larger than the cheque. The part of the loss that the lenders absorb
instead of the sponsor is shown as a separate "limited liability" bar
(= floored exit equity - unfloored exit equity >= 0). It is zero in every deal
where equity is still in the money, so the bridge always sums exactly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueBridge:
    entry_equity: float
    exit_equity: float
    revenue_growth: float
    margin_expansion: float
    multiple_expansion: float
    debt_paydown: float
    cash_generation: float
    transaction_fees: float  # negative number (value leakage)
    limited_liability: float = 0.0  # >= 0; loss absorbed by lenders in a wipe-out

    @property
    def ebitda_growth(self) -> float:
        return self.revenue_growth + self.margin_expansion

    @property
    def deleveraging(self) -> float:
        """Net debt reduction = debt repaid + increase in cash."""
        return self.debt_paydown + self.cash_generation

    @property
    def total_gain(self) -> float:
        return self.exit_equity - self.entry_equity

    def share_of_gain(self, component: float) -> float | None:
        """Component as % of the total gain, or None when there is no gain.

        Shares only make sense for a positive gain: dividing by a loss would
        flip the signs (value-creating drivers would show negative %).
        """
        return component / self.total_gain if self.total_gain > 0 else None

    @property
    def sum_of_components(self) -> float:
        return (
            self.ebitda_growth
            + self.multiple_expansion
            + self.deleveraging
            + self.transaction_fees
            + self.limited_liability
        )


def build_value_bridge(
    *,
    entry_equity: float,
    exit_equity: float,
    entry_revenue: float,
    entry_ebitda: float,
    exit_revenue: float,
    exit_ebitda: float,
    entry_multiple: float,
    exit_multiple: float,
    entry_debt: float,
    exit_debt: float,
    entry_cash: float,
    exit_cash: float,
    transaction_fees: float,
) -> ValueBridge:
    entry_margin = entry_ebitda / entry_revenue
    exit_margin = exit_ebitda / exit_revenue

    # EBITDA growth, valued at the ENTRY multiple, split into revenue and margin.
    revenue_growth = (exit_revenue - entry_revenue) * entry_margin * entry_multiple
    margin_expansion = exit_revenue * (exit_margin - entry_margin) * entry_multiple

    # Change in multiple, applied to EXIT EBITDA.
    multiple_expansion = (exit_multiple - entry_multiple) * exit_ebitda

    # Exit equity before the zero floor; the gap to the actual (floored) exit
    # equity is the loss the sponsor does not bear thanks to limited liability.
    unfloored_exit_equity = exit_multiple * exit_ebitda - (exit_debt - exit_cash)
    limited_liability = exit_equity - unfloored_exit_equity

    return ValueBridge(
        entry_equity=entry_equity,
        exit_equity=exit_equity,
        revenue_growth=revenue_growth,
        margin_expansion=margin_expansion,
        multiple_expansion=multiple_expansion,
        debt_paydown=entry_debt - exit_debt,
        cash_generation=exit_cash - entry_cash,
        transaction_fees=-transaction_fees,
        limited_liability=limited_liability,
    )
