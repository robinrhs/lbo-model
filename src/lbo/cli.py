"""Command line interface: `python -m lbo run config/example.yaml [--excel out.xlsx]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from lbo.config import ConfigError, load_config
from lbo.debt import LiquidityError
from lbo.model import LBOResult, run_model


def _money(x: float) -> str:
    """Banker-style: one decimal, thousands separator, negatives in brackets."""
    if abs(x) < 0.05:
        return "-"
    return f"({abs(x):,.1f})" if x < 0 else f"{x:,.1f}"


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _mult(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}x"


def _table(title: str, *columns: str, text_columns: tuple[int, ...] = (0,)) -> Table:
    """Label columns are left-aligned, number columns right-aligned."""
    table = Table(title=title, title_justify="left", title_style="bold", header_style="bold cyan")
    for i, col in enumerate(columns):
        table.add_column(col, justify="left" if i in text_columns else "right")
    return table


def sources_uses_table(result: LBOResult, currency: str) -> Table:
    su = result.base.sources_uses
    t = _table(
        f"Sources & Uses ({currency}m)",
        "Uses",
        "Amount",
        "Sources",
        "Amount",
        text_columns=(0, 2),
    )
    uses = [
        ("Purchase enterprise value", su.purchase_ev),
        ("Transaction fees", su.transaction_fees),
        ("Minimum cash", su.minimum_cash),
    ]
    sources = [*su.debt.items(), ("Sponsor equity", su.sponsor_equity)]
    for i in range(max(len(uses), len(sources))):
        u_name, u_val = uses[i] if i < len(uses) else ("", None)
        s_name, s_val = sources[i] if i < len(sources) else ("", None)
        t.add_row(
            u_name,
            "" if u_val is None else _money(u_val),
            s_name,
            "" if s_val is None else _money(s_val),
        )
    t.add_section()
    t.add_row("Total uses", _money(su.total_uses), "Total sources", _money(su.total_sources))
    return t


def projection_table(result: LBOResult, currency: str) -> Table:
    base = result.base
    years = [f"Y{op.year}" for op in base.operations]
    t = _table(f"Projection & debt schedule ({currency}m)", "", *years)
    ops, cfs = base.operations, base.schedule
    rows = [
        ("Revenue", [o.revenue for o in ops]),
        ("EBITDA", [o.ebitda for o in ops]),
        ("Cash interest", [-c.interest for c in cfs]),
        ("Cash taxes", [-c.cash_taxes for c in cfs]),
        ("Capex", [-c.capex for c in cfs]),
        ("Increase in NWC", [-c.change_nwc for c in cfs]),
        ("Levered free cash flow", [c.levered_fcf for c in cfs]),
        ("Debt repayment", [-c.total_repayment for c in cfs]),
        ("Ending debt", [c.ending_debt for c in cfs]),
        ("Ending cash", [c.ending_cash for c in cfs]),
    ]
    for label, values in rows:
        t.add_row(label, *(_money(v) for v in values))
    t.add_section()
    t.add_row("EBITDA margin", *(_pct(o.ebitda_margin) for o in ops))
    t.add_row(
        "Net debt / EBITDA",
        *(_mult((c.ending_debt - c.ending_cash) / c.ebitda) for c in cfs),
    )
    return t


def returns_table(result: LBOResult, currency: str) -> Table:
    r = result.base.returns
    t = _table(f"Returns ({currency}m)", "", "Value")
    t.add_row("Exit EBITDA", _money(r.exit_ebitda))
    t.add_row("Exit multiple", _mult(r.exit_multiple))
    t.add_row("Exit enterprise value", _money(r.exit_ev))
    t.add_row("Less: net debt at exit", _money(-r.net_debt_at_exit))
    t.add_row("Exit equity value", _money(r.exit_equity))
    t.add_row("Equity invested", _money(r.entry_equity))
    t.add_section()
    t.add_row("MOIC", _mult(r.moic))
    t.add_row(f"IRR ({r.holding_period_years}-year hold)", _pct(r.irr))
    return t


def bridge_table(result: LBOResult, currency: str) -> Table:
    b = result.base.bridge
    t = _table(f"Value creation bridge ({currency}m)", "", "Value", "% of gain")
    gain = b.total_gain
    rows = [
        ("Revenue growth", b.revenue_growth),
        ("Margin expansion", b.margin_expansion),
        ("Multiple expansion", b.multiple_expansion),
        ("Debt paydown", b.debt_paydown),
        ("Cash generation", b.cash_generation),
        ("Transaction fees", b.transaction_fees),
    ]
    for label, value in rows:
        t.add_row(label, _money(value), _pct(value / gain) if gain else "n/a")
    t.add_section()
    t.add_row("Total equity gain", _money(gain), _pct(1.0) if gain else "n/a")
    return t


def sensitivity_table(result: LBOResult) -> Table:
    s = result.sensitivity
    t = _table(
        "IRR sensitivity: entry multiple (rows) x exit multiple",
        "Entry \\ Exit",
        *(_mult(m) for m in s.exit_multiples),
    )
    for entry_multiple, row in zip(s.entry_multiples, s.irr, strict=True):
        t.add_row(_mult(entry_multiple), *(_pct(v) for v in row))
    return t


def print_summary(result: LBOResult, console: Console) -> None:
    config = result.base.config
    currency = config.company.currency
    console.print(f"\n[bold]LBO model: {config.company.name}[/bold]")
    entry, deal_exit = config.entry, config.exit
    console.print(
        f"Entry {_mult(entry.entry_multiple)} LTM EBITDA of {_money(entry.ltm_ebitda)}"
        f" | leverage {_mult(config.total_debt_x_ebitda)}"
        f" | exit {_mult(deal_exit.exit_multiple)} after {deal_exit.holding_period_years} years\n"
    )
    for table in (
        sources_uses_table(result, currency),
        projection_table(result, currency),
        returns_table(result, currency),
        bridge_table(result, currency),
        sensitivity_table(result),
    ):
        console.print(table)
        console.print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lbo", description="Transparent LBO model.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the model on a YAML assumptions file")
    run.add_argument("config", type=Path, help="path to the assumptions YAML")
    run.add_argument("--excel", type=Path, metavar="PATH", help="also export an Excel workbook")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console()
    try:
        config = load_config(args.config)
        result = run_model(config)
    except (ConfigError, LiquidityError) as err:
        console.print(f"[red]{err}[/red]")
        return 1

    print_summary(result, console)

    if args.excel:
        from lbo.excel import export_workbook

        path = export_workbook(result, args.excel)
        console.print(f"Excel workbook written to [bold]{path}[/bold]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
