"""Sensitivity of returns to entry and exit multiples.

Each cell re-runs the full model with one entry multiple (rows) and one exit
multiple (columns); everything else is unchanged. Debt is sized on EBITDA, so a
higher entry multiple means a higher price funded entirely with more equity,
which lowers returns. The centre cell is the base case by construction.

A cell is empty (None) only when that combination is not a valid deal, e.g.
when a very low entry multiple would make debt exceed the purchase price. A
valid deal in which the equity is wiped out at exit is NOT empty: it shows
MOIC 0.00x and IRR -100%.
"""

from __future__ import annotations

from dataclasses import dataclass

from lbo.config import ConfigError, DealConfig
from lbo.deal import run_deal


@dataclass(frozen=True)
class SensitivityTable:
    entry_multiples: list[float]
    exit_multiples: list[float]
    irr: list[list[float | None]]  # irr[row = entry][col = exit]
    moic: list[list[float | None]]


def multiple_grid(centre: float, step: float, steps: int) -> list[float]:
    """E.g. centre 10.0, step 0.5, steps 2 -> [9.0, 9.5, 10.0, 10.5, 11.0]."""
    return [round(centre + k * step, 6) for k in range(-steps, steps + 1)]


def build_sensitivity(config: DealConfig) -> SensitivityTable:
    s = config.sensitivity
    entry_multiples = multiple_grid(config.entry.entry_multiple, s.entry_multiple_step, s.steps)
    exit_multiples = multiple_grid(config.exit.exit_multiple, s.exit_multiple_step, s.steps)

    irr_rows: list[list[float | None]] = []
    moic_rows: list[list[float | None]] = []
    for entry_multiple in entry_multiples:
        irr_row: list[float | None] = []
        moic_row: list[float | None] = []
        for exit_multiple in exit_multiples:
            try:
                case = config.with_multiples(entry_multiple, exit_multiple)
                result = run_deal(case).returns
            except ConfigError:
                irr_row.append(None)
                moic_row.append(None)
                continue
            irr_row.append(result.irr)
            moic_row.append(result.moic)
        irr_rows.append(irr_row)
        moic_rows.append(moic_row)

    return SensitivityTable(
        entry_multiples=entry_multiples,
        exit_multiples=exit_multiples,
        irr=irr_rows,
        moic=moic_rows,
    )
