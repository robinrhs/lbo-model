"""Cash flow waterfall and debt schedule.

Each year the model walks down the same waterfall:

    EBITDA
  - Cash taxes            = max(0, (EBIT - interest) x tax rate)
  - Capex
  - Increase in NWC
  = Free cash flow before debt service
  - Cash interest         = sum over tranches of (rate x BEGINNING balance)
  = Cash available for debt repayment ("levered FCF")
  - Mandatory amortisation (each tranche: % of original principal, capped at balance)
  - Cash sweep            = sweep % x (cash above minimum cash), paid to sweepable
                            tranches in seniority order
  = Change in cash

Conventions (deliberate simplifications, see README):
* Interest is charged on the BEGINNING-of-year balance. This avoids the
  circular reference that average-balance interest creates (interest depends on
  repayment, which depends on cash flow, which depends on interest).
* Interest tax shield: interest is tax-deductible, so taxes are computed on
  EBIT minus interest. The shield is therefore already inside "cash taxes";
  it is reported separately for transparency but never subtracted twice.
  Losses are not carried forward (taxes are floored at zero).
* No interest income on cash, no revolver, no PIK interest.
"""

from __future__ import annotations

from dataclasses import dataclass

from lbo.config import DealConfig
from lbo.projection import OperatingYear
from lbo.transaction import SourcesAndUses


class LiquidityError(RuntimeError):
    """Raised when cash would turn negative (the model has no revolver)."""


@dataclass(frozen=True)
class TrancheYear:
    name: str
    beginning_balance: float
    interest: float
    mandatory_repayment: float
    sweep_repayment: float
    ending_balance: float


@dataclass(frozen=True)
class CashFlowYear:
    year: int
    ebitda: float
    ebit: float
    interest: float
    pre_tax_income: float
    cash_taxes: float
    interest_tax_shield: float
    capex: float
    change_nwc: float
    fcf_before_debt_service: float
    levered_fcf: float
    beginning_cash: float
    mandatory_repayment: float
    excess_cash: float  # cash above minimum after mandatory repayment
    sweep_repayment: float
    ending_cash: float
    tranches: tuple[TrancheYear, ...]

    @property
    def beginning_debt(self) -> float:
        return sum(t.beginning_balance for t in self.tranches)

    @property
    def ending_debt(self) -> float:
        return sum(t.ending_balance for t in self.tranches)

    @property
    def total_repayment(self) -> float:
        return self.mandatory_repayment + self.sweep_repayment


# --- small pure building blocks ----------------------------------------------


def cash_taxes(ebit: float, interest: float, tax_rate: float) -> float:
    """Taxes on pre-tax income (EBIT - interest). No refund when the result is a loss."""
    return max(0.0, (ebit - interest) * tax_rate)


def interest_tax_shield(ebit: float, interest: float, tax_rate: float) -> float:
    """Taxes saved because interest is deductible: unlevered taxes minus levered taxes."""
    return cash_taxes(ebit, 0.0, tax_rate) - cash_taxes(ebit, interest, tax_rate)


def mandatory_repayment(
    original_principal: float, amortization_pct: float, balance: float
) -> float:
    """Scheduled repayment: % of ORIGINAL principal, but never more than is still owed."""
    return min(original_principal * amortization_pct, balance)


def allocate_sweep(available: float, balances: list[float], sweepable: list[bool]) -> list[float]:
    """Pay `available` cash to sweepable tranches in seniority order (list order).

    The most senior tranche is repaid first; only once it is fully repaid does
    the next sweepable tranche receive anything.
    """
    payments: list[float] = []
    remaining = max(0.0, available)
    for balance, can_sweep in zip(balances, sweepable, strict=True):
        payment = min(remaining, balance) if can_sweep else 0.0
        payments.append(payment)
        remaining -= payment
    return payments


# --- the annual schedule -------------------------------------------------------


def build_debt_schedule(
    config: DealConfig, operations: list[OperatingYear], sources_uses: SourcesAndUses
) -> list[CashFlowYear]:
    tranches = config.debt.tranches
    tax_rate = config.operations.tax_rate
    minimum_cash = config.entry.minimum_cash
    sweep_pct = config.debt.cash_sweep_pct

    original = [sources_uses.debt[t.name] for t in tranches]
    balances = list(original)
    cash = sources_uses.minimum_cash  # cash on the balance sheet right after closing

    schedule: list[CashFlowYear] = []
    for op in operations:
        # 1) Interest on beginning-of-year balances (no circularity).
        interest_by_tranche = [b * t.interest_rate for b, t in zip(balances, tranches, strict=True)]
        interest = sum(interest_by_tranche)

        # 2) Taxes after the interest deduction; the shield is embedded here.
        taxes = cash_taxes(op.ebit, interest, tax_rate)
        shield = interest_tax_shield(op.ebit, interest, tax_rate)

        # 3) Free cash flow before and after interest.
        fcf_before_debt_service = op.ebitda - taxes - op.capex - op.change_nwc
        levered_fcf = fcf_before_debt_service - interest

        # 4) Mandatory amortisation is contractual and is paid first.
        mandatory = [
            mandatory_repayment(orig, t.mandatory_amortization_pct, bal)
            for orig, t, bal in zip(original, tranches, balances, strict=True)
        ]
        cash_after_mandatory = cash + levered_fcf - sum(mandatory)
        if cash_after_mandatory < 0:
            raise LiquidityError(
                f"Year {op.year}: cash would fall to {cash_after_mandatory:,.1f} after interest "
                "and mandatory amortisation. The model has no revolver; reduce leverage or "
                "amortisation."
            )

        # 5) Cash sweep: a share of the cash above the minimum balance prepays
        #    debt, senior first. The rest stays on the balance sheet.
        excess_cash = max(0.0, cash_after_mandatory - minimum_cash)
        balances_after_mandatory = [b - m for b, m in zip(balances, mandatory, strict=True)]
        sweep = allocate_sweep(
            excess_cash * sweep_pct, balances_after_mandatory, [t.sweep for t in tranches]
        )

        ending_balances = [b - s for b, s in zip(balances_after_mandatory, sweep, strict=True)]
        ending_cash = cash_after_mandatory - sum(sweep)

        schedule.append(
            CashFlowYear(
                year=op.year,
                ebitda=op.ebitda,
                ebit=op.ebit,
                interest=interest,
                pre_tax_income=op.ebit - interest,
                cash_taxes=taxes,
                interest_tax_shield=shield,
                capex=op.capex,
                change_nwc=op.change_nwc,
                fcf_before_debt_service=fcf_before_debt_service,
                levered_fcf=levered_fcf,
                beginning_cash=cash,
                mandatory_repayment=sum(mandatory),
                excess_cash=excess_cash,
                sweep_repayment=sum(sweep),
                ending_cash=ending_cash,
                tranches=tuple(
                    TrancheYear(
                        name=t.name,
                        beginning_balance=b,
                        interest=i,
                        mandatory_repayment=m,
                        sweep_repayment=s,
                        ending_balance=e,
                    )
                    for t, b, i, m, s, e in zip(
                        tranches,
                        balances,
                        interest_by_tranche,
                        mandatory,
                        sweep,
                        ending_balances,
                        strict=True,
                    )
                ),
            )
        )
        balances = ending_balances
        cash = ending_cash
    return schedule
