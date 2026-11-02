"""Run one LBO case end to end: sources & uses -> projection -> debt -> returns -> bridge."""

from __future__ import annotations

from dataclasses import dataclass

from lbo.bridge import ValueBridge, build_value_bridge
from lbo.config import DealConfig
from lbo.debt import CashFlowYear, build_debt_schedule
from lbo.projection import OperatingYear, project_operations
from lbo.returns import Returns, compute_returns
from lbo.transaction import SourcesAndUses, build_sources_and_uses


@dataclass(frozen=True)
class DealResult:
    config: DealConfig
    sources_uses: SourcesAndUses
    operations: list[OperatingYear]
    schedule: list[CashFlowYear]
    returns: Returns
    bridge: ValueBridge


def run_deal(config: DealConfig) -> DealResult:
    sources_uses = build_sources_and_uses(config)
    operations = project_operations(config)
    schedule = build_debt_schedule(config, operations, sources_uses)

    exit_year_ops = operations[-1]
    exit_year_cash = schedule[-1]

    returns = compute_returns(
        entry_equity=sources_uses.sponsor_equity,
        exit_ebitda=exit_year_ops.ebitda,
        exit_multiple=config.exit.exit_multiple,
        exit_debt=exit_year_cash.ending_debt,
        exit_cash=exit_year_cash.ending_cash,
        holding_period_years=config.exit.holding_period_years,
    )

    bridge = build_value_bridge(
        entry_equity=sources_uses.sponsor_equity,
        exit_equity=returns.exit_equity,
        entry_revenue=config.entry.ltm_revenue,
        entry_ebitda=config.entry.ltm_ebitda,
        exit_revenue=exit_year_ops.revenue,
        exit_ebitda=exit_year_ops.ebitda,
        entry_multiple=config.entry.entry_multiple,
        exit_multiple=config.exit.exit_multiple,
        entry_debt=sources_uses.total_debt,
        exit_debt=exit_year_cash.ending_debt,
        entry_cash=sources_uses.minimum_cash,
        exit_cash=exit_year_cash.ending_cash,
        transaction_fees=sources_uses.transaction_fees,
    )

    return DealResult(
        config=config,
        sources_uses=sources_uses,
        operations=operations,
        schedule=schedule,
        returns=returns,
        bridge=bridge,
    )
