"""Sources & uses of funds at closing.

Uses  = what the money is spent on:   purchase EV + transaction fees + minimum cash
Sources = where the money comes from: debt tranches + sponsor equity

Sponsor equity is the plug: debt is sized by lenders as a multiple of EBITDA,
and the private equity fund contributes whatever is still missing. By
construction, total sources always equal total uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from lbo.config import DealConfig


@dataclass(frozen=True)
class SourcesAndUses:
    # Uses
    purchase_ev: float
    transaction_fees: float
    minimum_cash: float
    # Sources (tranche name -> amount, in seniority order)
    debt: dict[str, float]
    sponsor_equity: float

    @property
    def total_uses(self) -> float:
        return self.purchase_ev + self.transaction_fees + self.minimum_cash

    @property
    def total_debt(self) -> float:
        return sum(self.debt.values())

    @property
    def total_sources(self) -> float:
        return self.total_debt + self.sponsor_equity


def build_sources_and_uses(config: DealConfig) -> SourcesAndUses:
    ebitda = config.entry.ltm_ebitda

    # Purchase price on a cash-free / debt-free basis: EV = EBITDA x multiple.
    purchase_ev = ebitda * config.entry.entry_multiple
    transaction_fees = purchase_ev * config.entry.transaction_fees_pct_ev
    minimum_cash = config.entry.minimum_cash
    total_uses = purchase_ev + transaction_fees + minimum_cash

    # Each tranche is sized as "x times entry EBITDA".
    debt = {t.name: t.amount_x_ebitda * ebitda for t in config.debt.tranches}

    # Equity fills the gap between what is spent and what is borrowed.
    sponsor_equity = total_uses - sum(debt.values())

    return SourcesAndUses(
        purchase_ev=purchase_ev,
        transaction_fees=transaction_fees,
        minimum_cash=minimum_cash,
        debt=debt,
        sponsor_equity=sponsor_equity,
    )
