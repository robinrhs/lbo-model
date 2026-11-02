"""Export the model to a formatted Excel workbook (openpyxl).

Layout follows common banking conventions:
* blue font = hard-coded input, black font = calculated
* one sheet per schedule, years in columns, labels in column A
* negatives in brackets, multiples as "x", frozen header rows/label column

The cells contain the VALUES computed by the Python model, not live Excel
formulas. The workbook is a presentation of the results; the Python code
(and its tests) is the single source of truth for the calculations.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from lbo.bridge import ValueBridge
from lbo.model import LBOResult

# --- styles ----------------------------------------------------------------------

NAVY = "1F3864"
INPUT_BLUE = "0000FF"
FONT_NAME = "Calibri"

TITLE_FONT = Font(name=FONT_NAME, size=14, bold=True, color=NAVY)
SUBTITLE_FONT = Font(name=FONT_NAME, size=9, italic=True, color="595959")
HEADER_FONT = Font(name=FONT_NAME, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
SECTION_FONT = Font(name=FONT_NAME, bold=True, color=NAVY)
CALC_FONT = Font(name=FONT_NAME, color="000000")
BOLD_FONT = Font(name=FONT_NAME, bold=True, color="000000")
INPUT_FONT = Font(name=FONT_NAME, color=INPUT_BLUE)
NOTE_FONT = Font(name=FONT_NAME, size=9, italic=True, color="595959")
TOTAL_BORDER = Border(top=Side(style="thin"), bottom=Side(style="double"))
SUBTOTAL_BORDER = Border(top=Side(style="thin"))
HIGHLIGHT_FILL = PatternFill("solid", fgColor="FFF2CC")

# Number formats: positive_;(negative);zero
MONEY = '#,##0.0_);(#,##0.0);"-"_)'
PCT = '0.0%_);(0.0%);"-"_)'
MULT = '0.00"x"_);(0.00"x");"-"_)'
INTEGER = "0_)"

LABEL_WIDTH = 36
VALUE_WIDTH = 13
HEADER_ROW = 4  # rows 1-2 title/subtitle, row 4 column headers


# --- low-level helpers -------------------------------------------------------------


def _new_sheet(wb: Workbook, name: str, title: str, subtitle: str) -> Worksheet:
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = SUBTITLE_FONT
    return ws


def _header(ws: Worksheet, row: int, labels: Iterable[str]) -> None:
    for col, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=col, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="left" if col == 1 else "right")


def _section(ws: Worksheet, row: int, label: str) -> None:
    ws.cell(row=row, column=1, value=label).font = SECTION_FONT


def _row(
    ws: Worksheet,
    row: int,
    label: str,
    values: Iterable[float | str | None],
    fmt: str = MONEY,
    *,
    font: Font = CALC_FONT,
    border: Border | None = None,
    start_col: int = 2,
    indent: int = 0,
) -> None:
    label_cell = ws.cell(row=row, column=1, value=label)
    label_cell.font = BOLD_FONT if font is BOLD_FONT else CALC_FONT
    label_cell.alignment = Alignment(indent=indent)
    if border is not None:
        label_cell.border = border
    for offset, value in enumerate(values):
        if isinstance(value, float):
            value += 0.0  # turns -0.0 into 0.0 so zeros display as "-", not "(0.0)"
        cell = ws.cell(row=row, column=start_col + offset, value=value)
        cell.font = font
        cell.number_format = fmt
        cell.alignment = Alignment(horizontal="right")
        if border is not None:
            cell.border = border


def _widths(ws: Worksheet, n_value_cols: int, value_width: int = VALUE_WIDTH) -> None:
    ws.column_dimensions["A"].width = LABEL_WIDTH
    for col in range(2, 2 + n_value_cols):
        ws.column_dimensions[get_column_letter(col)].width = value_width


def _note(ws: Worksheet, row: int, text: str) -> None:
    ws.cell(row=row, column=1, value=text).font = NOTE_FONT


# --- sheets --------------------------------------------------------------------------


def _assumptions_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    n = cfg.exit.holding_period_years
    ws = _new_sheet(wb, "Assumptions", f"{cfg.company.name}: Assumptions", subtitle)
    _header(ws, HEADER_ROW, ["Input", "Value"])

    r = HEADER_ROW + 1
    _section(ws, r, "Transaction")
    entry_inputs = [
        ("LTM revenue", cfg.entry.ltm_revenue, MONEY),
        ("LTM EBITDA", cfg.entry.ltm_ebitda, MONEY),
        ("Entry EV / EBITDA", cfg.entry.entry_multiple, MULT),
        ("Transaction fees (% of EV)", cfg.entry.transaction_fees_pct_ev, PCT),
        ("Minimum cash", cfg.entry.minimum_cash, MONEY),
    ]
    for label, value, fmt in entry_inputs:
        r += 1
        _row(ws, r, label, [value], fmt, font=INPUT_FONT, indent=1)

    r += 2
    _section(ws, r, "Exit")
    r += 1
    _row(ws, r, "Holding period (years)", [n], INTEGER, font=INPUT_FONT, indent=1)
    r += 1
    _row(ws, r, "Exit EV / EBITDA", [cfg.exit.exit_multiple], MULT, font=INPUT_FONT, indent=1)

    r += 2
    _section(ws, r, "Operations")
    ops = cfg.operations
    for label, value, fmt in [
        ("D&A (% of revenue)", ops.da_pct_revenue, PCT),
        ("Capex (% of revenue)", ops.capex_pct_revenue, PCT),
        ("NWC (% of change in revenue)", ops.nwc_pct_revenue_change, PCT),
        ("Tax rate", ops.tax_rate, PCT),
    ]:
        r += 1
        _row(ws, r, label, [value], fmt, font=INPUT_FONT, indent=1)

    r += 2
    _header(ws, r, ["Operating plan", *(f"Year {t}" for t in range(1, n + 1))])
    r += 1
    _row(ws, r, "Revenue growth", cfg.revenue_growth_by_year(), PCT, font=INPUT_FONT, indent=1)
    r += 1
    _row(ws, r, "EBITDA margin", cfg.ebitda_margin_by_year(), PCT, font=INPUT_FONT, indent=1)

    r += 2
    _header(ws, r, ["Debt tranche (senior first)", "x EBITDA", "Rate", "Amort. p.a.", "Sweep"])
    for tranche in cfg.debt.tranches:
        r += 1
        _row(
            ws,
            r,
            tranche.name,
            [tranche.amount_x_ebitda],
            MULT,
            font=INPUT_FONT,
            indent=1,
        )
        _row(
            ws,
            r,
            tranche.name,
            [tranche.interest_rate, tranche.mandatory_amortization_pct],
            PCT,
            font=INPUT_FONT,
            start_col=3,
            indent=1,
        )
        ws.cell(row=r, column=5, value="Yes" if tranche.sweep else "No").font = INPUT_FONT
        ws.cell(row=r, column=5).alignment = Alignment(horizontal="right")
    r += 1
    _row(ws, r, "Cash sweep (% of excess cash)", [cfg.debt.cash_sweep_pct], PCT, font=INPUT_FONT)

    r += 2
    _note(ws, r, "Blue font = hard-coded input. Black font = calculated by the Python model.")
    _widths(ws, max(n, 4))
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _sources_uses_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    su = result.base.sources_uses
    ebitda = cfg.entry.ltm_ebitda
    ws = _new_sheet(wb, "Sources & Uses", f"{cfg.company.name}: Sources & Uses", subtitle)
    _header(ws, HEADER_ROW, ["Uses of funds", "Amount", "% of total", "x EBITDA"])

    r = HEADER_ROW
    uses = [
        ("Purchase enterprise value", su.purchase_ev),
        ("Transaction fees", su.transaction_fees),
        ("Minimum cash", su.minimum_cash),
    ]
    for label, value in uses:
        r += 1
        _row(ws, r, label, [value], MONEY, indent=1)
        _row(ws, r, label, [value / su.total_uses], PCT, start_col=3, indent=1)
        _row(ws, r, label, [value / ebitda], MULT, start_col=4, indent=1)
    r += 1
    _row(ws, r, "Total uses", [su.total_uses], MONEY, font=BOLD_FONT, border=TOTAL_BORDER)
    _row(ws, r, "Total uses", [1.0], PCT, font=BOLD_FONT, border=TOTAL_BORDER, start_col=3)
    _row(
        ws,
        r,
        "Total uses",
        [su.total_uses / ebitda],
        MULT,
        font=BOLD_FONT,
        border=TOTAL_BORDER,
        start_col=4,
    )

    r += 2
    _header(ws, r, ["Sources of funds", "Amount", "% of total", "x EBITDA"])
    sources = [*su.debt.items(), ("Sponsor equity", su.sponsor_equity)]
    for label, value in sources:
        r += 1
        _row(ws, r, label, [value], MONEY, indent=1)
        _row(ws, r, label, [value / su.total_sources], PCT, start_col=3, indent=1)
        _row(ws, r, label, [value / ebitda], MULT, start_col=4, indent=1)
    r += 1
    _row(ws, r, "Total sources", [su.total_sources], MONEY, font=BOLD_FONT, border=TOTAL_BORDER)
    _row(ws, r, "Total sources", [1.0], PCT, font=BOLD_FONT, border=TOTAL_BORDER, start_col=3)
    _row(
        ws,
        r,
        "Total sources",
        [su.total_sources / ebitda],
        MULT,
        font=BOLD_FONT,
        border=TOTAL_BORDER,
        start_col=4,
    )

    r += 2
    _note(ws, r, "Sponsor equity is the plug: total uses less total debt.")
    _widths(ws, 3)
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _projection_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    ops = result.base.operations
    ws = _new_sheet(wb, "Projection", f"{cfg.company.name}: Operating projection", subtitle)
    _header(ws, HEADER_ROW, ["", "LTM", *(f"Year {o.year}" for o in ops)])

    ltm_rev, ltm_ebitda = cfg.entry.ltm_revenue, cfg.entry.ltm_ebitda
    rows: list[tuple[str, list, str, Font, Border | None]] = [
        ("Revenue", [ltm_rev, *(o.revenue for o in ops)], MONEY, BOLD_FONT, None),
        ("Growth %", [None, *(o.revenue_growth for o in ops)], PCT, CALC_FONT, None),
        ("EBITDA", [ltm_ebitda, *(o.ebitda for o in ops)], MONEY, BOLD_FONT, None),
        ("EBITDA margin %", [ltm_ebitda / ltm_rev, *(o.ebitda_margin for o in ops)], PCT,
         CALC_FONT, None),
        ("Less: D&A", [None, *(-o.da for o in ops)], MONEY, CALC_FONT, None),
        ("EBIT", [None, *(o.ebit for o in ops)], MONEY, BOLD_FONT, SUBTOTAL_BORDER),
        ("", [], MONEY, CALC_FONT, None),
        ("Capex", [None, *(-o.capex for o in ops)], MONEY, CALC_FONT, None),
        ("Increase in net working capital", [None, *(-o.change_nwc for o in ops)], MONEY,
         CALC_FONT, None),
    ]  # fmt: skip
    r = HEADER_ROW
    for label, values, fmt, font, border in rows:
        r += 1
        _row(ws, r, label, values, fmt, font=font, border=border)

    r += 2
    _note(ws, r, "Cash outflows shown as negatives (in brackets).")
    _widths(ws, len(ops) + 1)
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _debt_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    sched = result.base.schedule
    ws = _new_sheet(wb, "Debt Schedule", f"{cfg.company.name}: Cash flow & debt schedule", subtitle)
    _header(ws, HEADER_ROW, ["Cash flow waterfall", *(f"Year {y.year}" for y in sched)])

    waterfall: list[tuple[str, list[float], Font, Border | None]] = [
        ("EBITDA", [y.ebitda for y in sched], BOLD_FONT, None),
        ("Less: cash taxes", [-y.cash_taxes for y in sched], CALC_FONT, None),
        ("Less: capex", [-y.capex for y in sched], CALC_FONT, None),
        ("Less: increase in NWC", [-y.change_nwc for y in sched], CALC_FONT, None),
        ("FCF before debt service", [y.fcf_before_debt_service for y in sched], BOLD_FONT,
         SUBTOTAL_BORDER),
        ("Less: cash interest", [-y.interest for y in sched], CALC_FONT, None),
        ("Levered free cash flow", [y.levered_fcf for y in sched], BOLD_FONT, SUBTOTAL_BORDER),
        ("Less: mandatory amortisation", [-y.mandatory_repayment for y in sched], CALC_FONT,
         None),
        ("Less: cash sweep", [-y.sweep_repayment for y in sched], CALC_FONT, None),
        ("Change in cash", [y.ending_cash - y.beginning_cash for y in sched], BOLD_FONT,
         SUBTOTAL_BORDER),
        ("", [], CALC_FONT, None),
        ("Beginning cash", [y.beginning_cash for y in sched], CALC_FONT, None),
        ("Ending cash", [y.ending_cash for y in sched], BOLD_FONT, TOTAL_BORDER),
        ("", [], CALC_FONT, None),
        ("Memo: excess cash above minimum", [y.excess_cash for y in sched], CALC_FONT, None),
        ("Memo: interest tax shield (in taxes)", [y.interest_tax_shield for y in sched],
         CALC_FONT, None),
    ]  # fmt: skip
    r = HEADER_ROW
    for label, values, font, border in waterfall:
        r += 1
        _row(ws, r, label, values, MONEY, font=font, border=border)

    for i, tranche_cfg in enumerate(cfg.debt.tranches):
        r += 2
        rate = f"{tranche_cfg.interest_rate:.2%}"
        _header(ws, r, [f"{tranche_cfg.name} ({rate})", *(f"Year {y.year}" for y in sched)])
        lines = [
            ("Beginning balance", [y.tranches[i].beginning_balance for y in sched], CALC_FONT,
             None),
            ("Mandatory amortisation", [-y.tranches[i].mandatory_repayment for y in sched],
             CALC_FONT, None),
            ("Cash sweep", [-y.tranches[i].sweep_repayment for y in sched], CALC_FONT, None),
            ("Ending balance", [y.tranches[i].ending_balance for y in sched], BOLD_FONT,
             TOTAL_BORDER),
            ("Interest (on beginning balance)", [y.tranches[i].interest for y in sched],
             CALC_FONT, None),
        ]  # fmt: skip
        for label, values, font, border in lines:
            r += 1
            _row(ws, r, label, values, MONEY, font=font, border=border, indent=1)

    r += 2
    _header(ws, r, ["Credit statistics", *(f"Year {y.year}" for y in sched)])
    stats = [
        ("Total debt", [y.ending_debt for y in sched], MONEY),
        ("Net debt", [y.ending_debt - y.ending_cash for y in sched], MONEY),
        ("Total debt / EBITDA", [y.ending_debt / y.ebitda for y in sched], MULT),
        ("Net debt / EBITDA", [(y.ending_debt - y.ending_cash) / y.ebitda for y in sched], MULT),
        ("EBITDA / cash interest", [_safe_div(y.ebitda, y.interest) for y in sched], MULT),
        ("Cumulative debt repaid", _cumulative_paydown(result), PCT),
    ]
    for label, values, fmt in stats:
        r += 1
        _row(ws, r, label, values, fmt, indent=1)

    r += 2
    _note(ws, r, "Interest is charged on beginning-of-year balances (no circularity).")
    _note(ws, r + 1, "Taxes = max(0, (EBIT - interest) x tax rate); the shield is inside taxes.")
    _widths(ws, len(sched))
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def _cumulative_paydown(result: LBOResult) -> list[float]:
    initial = result.base.sources_uses.total_debt
    return [(initial - y.ending_debt) / initial if initial else 0.0 for y in result.base.schedule]


def _returns_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    ret = result.base.returns
    ws = _new_sheet(wb, "Returns", f"{cfg.company.name}: Exit & returns", subtitle)
    _header(ws, HEADER_ROW, ["Exit valuation", "Value"])

    r = HEADER_ROW
    exit_rows = [
        ("Exit-year EBITDA", ret.exit_ebitda, MONEY, CALC_FONT, None),
        ("Exit EV / EBITDA", ret.exit_multiple, MULT, INPUT_FONT, None),
        ("Exit enterprise value", ret.exit_ev, MONEY, BOLD_FONT, SUBTOTAL_BORDER),
        ("Less: debt at exit", -ret.exit_debt, MONEY, CALC_FONT, None),
        ("Plus: cash at exit", ret.exit_cash, MONEY, CALC_FONT, None),
        ("Exit equity value", ret.exit_equity, MONEY, BOLD_FONT, TOTAL_BORDER),
    ]
    if ret.is_total_loss:
        # Keep the column adding up: the shortfall is borne by lenders, not equity.
        floor = (
            "Plus: shortfall borne by lenders (limited liability)",
            ret.exit_equity - ret.equity_value_before_floor,
            MONEY,
            CALC_FONT,
            None,
        )
        exit_rows.insert(len(exit_rows) - 1, floor)
    for label, value, fmt, font, border in exit_rows:
        r += 1
        _row(ws, r, label, [value], fmt, font=font, border=border)

    r += 2
    flows = ret.equity_cash_flows
    _header(ws, r, ["Sponsor equity cash flows", *(f"Year {t}" for t in range(len(flows)))])
    r += 1
    _row(ws, r, "Equity (invested) / returned", list(flows), MONEY, font=BOLD_FONT)

    r += 2
    _header(ws, r, ["Returns", "Value"])
    r += 1
    _row(ws, r, "Equity invested", [ret.entry_equity], MONEY)
    r += 1
    _row(ws, r, "Exit equity value", [ret.exit_equity], MONEY)
    r += 1
    _row(ws, r, "MOIC", [ret.moic], MULT, font=BOLD_FONT)
    r += 1
    _row(ws, r, f"IRR ({ret.holding_period_years}-year hold)", [ret.irr], PCT, font=BOLD_FONT)

    r += 2
    _note(ws, r, "IRR solves NPV(equity cash flows) = 0. No interim dividends are assumed.")
    _note(
        ws,
        r + 1,
        "Exit equity is floored at zero (limited liability); a total loss shows MOIC 0.00x "
        "and IRR -100%.",
    )
    _widths(ws, len(flows))
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _share(bridge: ValueBridge, value: float) -> float | str:
    share = bridge.share_of_gain(value)
    return "n/a" if share is None else share


def _bridge_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    b = result.base.bridge
    ws = _new_sheet(wb, "Bridge", f"{cfg.company.name}: Value creation bridge", subtitle)
    _header(ws, HEADER_ROW, ["Equity value bridge", "Value", "% of gain"])

    gain = b.total_gain
    r = HEADER_ROW + 1
    _row(ws, r, "Entry equity", [b.entry_equity], MONEY, font=BOLD_FONT)
    components = [
        ("Revenue growth", b.revenue_growth),
        ("Margin expansion", b.margin_expansion),
        ("Multiple expansion", b.multiple_expansion),
        ("Debt paydown", b.debt_paydown),
        ("Cash generation", b.cash_generation),
        ("Transaction fees", b.transaction_fees),
    ]
    if b.limited_liability:  # only in a wipe-out: loss borne by lenders, not the sponsor
        components.append(("Limited liability (loss absorbed by lenders)", b.limited_liability))
    for label, value in components:
        r += 1
        _row(ws, r, label, [value], MONEY, indent=1)
        _row(ws, r, label, [_share(b, value)], PCT, start_col=3, indent=1)
    r += 1
    _row(ws, r, "Exit equity", [b.exit_equity], MONEY, font=BOLD_FONT, border=TOTAL_BORDER)

    r += 2
    _header(ws, r, ["Summary", "Value", "% of gain"])
    summary = [
        ("EBITDA growth (revenue + margin)", b.ebitda_growth),
        ("Multiple expansion", b.multiple_expansion),
        ("Deleveraging (net debt reduction)", b.deleveraging),
        ("Transaction fees", b.transaction_fees),
    ]
    if b.limited_liability:
        summary.append(("Limited liability (loss absorbed by lenders)", b.limited_liability))
    for label, value in summary:
        r += 1
        _row(ws, r, label, [value], MONEY, indent=1)
        _row(ws, r, label, [_share(b, value)], PCT, start_col=3, indent=1)
    r += 1
    _row(ws, r, "Total equity gain", [gain], MONEY, font=BOLD_FONT, border=TOTAL_BORDER)
    _row(
        ws,
        r,
        "Total equity gain",
        [_share(b, gain)],
        PCT,
        font=BOLD_FONT,
        border=TOTAL_BORDER,
        start_col=3,
    )

    r += 2
    notes = [
        "Order of decomposition: EBITDA growth is valued at the ENTRY multiple;",
        "multiple expansion is applied to EXIT EBITDA; within EBITDA growth, revenue",
        "growth uses the entry margin and margin expansion uses exit revenue.",
        "Components sum exactly to exit equity less entry equity.",
        "% of gain is shown only when the total gain is positive (n/a for a loss).",
    ]
    for i, text in enumerate(notes):
        _note(ws, r + i, text)
    _widths(ws, 2)
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


def _grid(
    ws: Worksheet,
    top: int,
    title: str,
    entry_multiples: list[float],
    exit_multiples: list[float],
    values: list[list[float | None]],
    fmt: str,
) -> int:
    _header(ws, top, [title, *(f"{m:.2f}x" for m in exit_multiples)])
    centre = len(entry_multiples) // 2
    r = top
    for i, (entry_multiple, row) in enumerate(zip(entry_multiples, values, strict=True)):
        r += 1
        label = ws.cell(row=r, column=1, value=entry_multiple)
        label.number_format = MULT
        label.font = BOLD_FONT
        label.alignment = Alignment(horizontal="left")
        for j, value in enumerate(row):
            cell = ws.cell(row=r, column=2 + j, value="n/a" if value is None else value)
            cell.number_format = fmt
            cell.alignment = Alignment(horizontal="right")
            cell.font = BOLD_FONT if (i == centre and j == centre) else CALC_FONT
            if i == centre and j == centre:
                cell.fill = HIGHLIGHT_FILL
    return r


def _sensitivity_sheet(wb: Workbook, result: LBOResult, subtitle: str) -> None:
    cfg = result.base.config
    s = result.sensitivity
    ws = _new_sheet(wb, "Sensitivity", f"{cfg.company.name}: Returns sensitivity", subtitle)
    end = _grid(
        ws, HEADER_ROW, "IRR: entry (rows) / exit (cols)", s.entry_multiples, s.exit_multiples,
        s.irr, PCT,
    )  # fmt: skip
    end = _grid(
        ws, end + 2, "MOIC: entry (rows) / exit (cols)", s.entry_multiples, s.exit_multiples,
        s.moic, MULT,
    )  # fmt: skip
    _note(ws, end + 2, "Highlighted cell = base case. Debt quantum is held at x EBITDA, so a")
    _note(ws, end + 3, "higher entry multiple is funded entirely with additional equity.")
    _widths(ws, len(s.exit_multiples))
    ws.column_dimensions["A"].width = 30
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=2)


# --- public API ------------------------------------------------------------------


def build_workbook(result: LBOResult) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)  # start without the default empty sheet
    currency = result.base.config.company.currency
    subtitle = f"{currency} millions unless stated. Values computed by lbo-model (Python)."
    _assumptions_sheet(wb, result, subtitle)
    _sources_uses_sheet(wb, result, subtitle)
    _projection_sheet(wb, result, subtitle)
    _debt_sheet(wb, result, subtitle)
    _returns_sheet(wb, result, subtitle)
    _bridge_sheet(wb, result, subtitle)
    _sensitivity_sheet(wb, result, subtitle)
    return wb


def export_workbook(result: LBOResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    build_workbook(result).save(path)
    return path
