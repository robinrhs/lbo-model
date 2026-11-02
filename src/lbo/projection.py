"""Operating projection: revenue down to EBIT, plus capex and working capital.

This part is independent of the financing. It answers "how much cash does the
business generate before anybody is paid interest?". The financing layer
(interest, taxes, debt repayment) is in `debt.py`.

Per projection year t = 1..N:
    Revenue_t   = Revenue_{t-1} x (1 + growth_t)        (Revenue_0 = LTM revenue)
    EBITDA_t    = Revenue_t x EBITDA margin_t
    D&A_t       = Revenue_t x D&A %
    EBIT_t      = EBITDA_t - D&A_t
    Capex_t     = Revenue_t x capex %
    dNWC_t      = (Revenue_t - Revenue_{t-1}) x NWC %   (cash outflow when positive)
"""

from __future__ import annotations

from dataclasses import dataclass

from lbo.config import DealConfig


@dataclass(frozen=True)
class OperatingYear:
    year: int
    revenue: float
    revenue_growth: float
    ebitda: float
    ebitda_margin: float
    da: float
    ebit: float
    capex: float
    change_nwc: float


def project_operations(config: DealConfig) -> list[OperatingYear]:
    ops = config.operations
    growth_by_year = config.revenue_growth_by_year()
    margin_by_year = config.ebitda_margin_by_year()

    years: list[OperatingYear] = []
    previous_revenue = config.entry.ltm_revenue
    for t, (growth, margin) in enumerate(zip(growth_by_year, margin_by_year, strict=True), 1):
        revenue = previous_revenue * (1 + growth)
        ebitda = revenue * margin
        # D&A is a non-cash expense: it reduces EBIT (and therefore taxes) but
        # not cash. Capex is the actual cash spent on fixed assets.
        da = revenue * ops.da_pct_revenue
        capex = revenue * ops.capex_pct_revenue
        # Extra revenue requires extra receivables/inventory: that investment
        # in working capital is a cash outflow.
        change_nwc = (revenue - previous_revenue) * ops.nwc_pct_revenue_change
        years.append(
            OperatingYear(
                year=t,
                revenue=revenue,
                revenue_growth=growth,
                ebitda=ebitda,
                ebitda_margin=margin,
                da=da,
                ebit=ebitda - da,
                capex=capex,
                change_nwc=change_nwc,
            )
        )
        previous_revenue = revenue
    return years
