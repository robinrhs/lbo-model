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

    @property
    def sum_of_components(self) -> float:
        return (
            self.ebitda_growth + self.multiple_expansion + self.deleveraging + self.transaction_fees
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

    return ValueBridge(
        entry_equity=entry_equity,
        exit_equity=exit_equity,
        revenue_growth=revenue_growth,
        margin_expansion=margin_expansion,
        multiple_expansion=multiple_expansion,
        debt_paydown=entry_debt - exit_debt,
        cash_generation=exit_cash - entry_cash,
        transaction_fees=-transaction_fees,
    )
