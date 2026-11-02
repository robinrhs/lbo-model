"""Deal assumptions: schema, validation and YAML loading.

Every number the model uses comes from one YAML file. The classes below describe
which inputs exist, what units they are in and which ranges make economic sense.
If an input is missing or implausible (e.g. a negative multiple), loading fails
with a message that names the offending field.

Units: all money amounts are in the deal currency, in millions. Rates and
percentages are decimals (0.30 = 30%). Multiples are plain numbers (10.0 = 10.0x).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ConfigError(ValueError):
    """Raised when the assumptions file cannot be read or fails validation."""


class _Strict(BaseModel):
    # Unknown keys are rejected so that a typo like "exit_multple" is caught
    # instead of being silently ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class Company(_Strict):
    name: str = "Generic Mid-Market Co."
    currency: str = "EUR"


class Entry(_Strict):
    """What we buy and what it costs."""

    # Last-twelve-months (LTM) figures at closing. Entry EBITDA is the basis for
    # both the purchase price (EBITDA x multiple) and the debt sizing (x EBITDA).
    ltm_revenue: float = Field(gt=0)
    ltm_ebitda: float = Field(gt=0)
    # Enterprise value / EBITDA paid at entry.
    entry_multiple: float = Field(gt=0)
    # Advisory, legal, due diligence and financing fees, as % of entry EV.
    # Treated as a cash cost at closing that is funded by the sponsor.
    transaction_fees_pct_ev: float = Field(default=0.0, ge=0, lt=0.2)
    # The target is bought cash-free / debt-free, so the operating cash the
    # business needs on day one has to be funded as part of the uses.
    minimum_cash: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _ebitda_below_revenue(self) -> Entry:
        if self.ltm_ebitda >= self.ltm_revenue:
            raise ValueError("ltm_ebitda must be smaller than ltm_revenue (margin below 100%)")
        return self


class Operations(_Strict):
    """Operating plan for the holding period.

    `revenue_growth` and `ebitda_margin` accept either one number (used for every
    year) or a list with exactly one value per projection year.
    """

    revenue_growth: float | list[float]
    ebitda_margin: float | list[float]
    # D&A and capex as % of revenue in the same year.
    da_pct_revenue: float = Field(ge=0, lt=1)
    capex_pct_revenue: float = Field(ge=0, lt=1)
    # Net working capital as % of the *change* in revenue: growing companies tie
    # up more receivables and inventory, which consumes cash.
    nwc_pct_revenue_change: float = Field(ge=-1, le=1)
    tax_rate: float = Field(ge=0, lt=1)

    @field_validator("revenue_growth")
    @classmethod
    def _growth_range(cls, value: float | list[float]) -> float | list[float]:
        for g in value if isinstance(value, list) else [value]:
            if not -0.5 < g < 1.0:
                raise ValueError(f"revenue growth {g} is outside the plausible range (-50%, 100%)")
        return value

    @field_validator("ebitda_margin")
    @classmethod
    def _margin_range(cls, value: float | list[float]) -> float | list[float]:
        for m in value if isinstance(value, list) else [value]:
            if not 0 < m < 1:
                raise ValueError(f"EBITDA margin {m} must be between 0 and 1")
        return value


class Exit(_Strict):
    holding_period_years: int = Field(ge=1, le=15)
    # EV / EBITDA at which the business is sold, applied to final-year EBITDA.
    exit_multiple: float = Field(gt=0)


class Tranche(_Strict):
    """One layer of acquisition debt. List tranches from most to least senior."""

    name: str
    # Debt size as a multiple of entry (LTM) EBITDA, the way lenders quote it.
    amount_x_ebitda: float = Field(ge=0)
    # Annual cash interest rate (fixed, all-in: base rate + margin).
    interest_rate: float = Field(ge=0, lt=0.5)
    # Scheduled repayment per year, as % of the ORIGINAL principal.
    mandatory_amortization_pct: float = Field(default=0.0, ge=0, le=1)
    # Whether this tranche can be prepaid from the excess cash sweep.
    # Senior bank debt usually can; bonds / mezzanine are usually non-call.
    sweep: bool = True


class Debt(_Strict):
    tranches: list[Tranche] = Field(min_length=1)
    # Share of the cash balance above minimum cash (after interest and mandatory
    # amortisation, INCLUDING cash retained in earlier years) used each year to
    # prepay sweepable tranches in seniority order. 0 = no sweep, 1 = full sweep.
    # Note: this is a balance-based sweep, not a credit-agreement "excess cash
    # flow" sweep on the year's flow only; see debt.py and the README.
    cash_sweep_pct: float = Field(default=0.0, ge=0, le=1)

    @field_validator("tranches")
    @classmethod
    def _unique_names(cls, tranches: list[Tranche]) -> list[Tranche]:
        names = [t.name for t in tranches]
        if len(set(names)) != len(names):
            raise ValueError(f"tranche names must be unique, got {names}")
        return tranches


class Sensitivity(_Strict):
    # Grid around the base case: centre +/- `steps` x `step` turns of EBITDA.
    entry_multiple_step: float = Field(default=0.5, gt=0)
    exit_multiple_step: float = Field(default=0.5, gt=0)
    steps: int = Field(default=2, ge=1, le=5)


class DealConfig(_Strict):
    company: Company = Company()
    entry: Entry
    operations: Operations
    exit: Exit
    debt: Debt
    sensitivity: Sensitivity = Sensitivity()

    @model_validator(mode="after")
    def _check_consistency(self) -> DealConfig:
        n = self.exit.holding_period_years
        for field_name in ("revenue_growth", "ebitda_margin"):
            value = getattr(self.operations, field_name)
            if isinstance(value, list) and len(value) != n:
                raise ValueError(
                    f"operations.{field_name} has {len(value)} values but "
                    f"exit.holding_period_years is {n}; give one value per year or a single number"
                )
        # Debt cannot exceed what is being paid; the sponsor must put in equity.
        total_debt = self.total_debt_x_ebitda * self.entry.ltm_ebitda
        total_uses = (
            self.entry_ev * (1 + self.entry.transaction_fees_pct_ev) + self.entry.minimum_cash
        )
        if total_debt >= total_uses:
            raise ValueError(
                f"total debt ({total_debt:,.1f}) is not below total uses ({total_uses:,.1f}); "
                "sponsor equity would be zero or negative"
            )
        return self

    # --- convenience accessors (pure derivations from inputs) ---------------

    @property
    def entry_ev(self) -> float:
        return self.entry.ltm_ebitda * self.entry.entry_multiple

    @property
    def total_debt_x_ebitda(self) -> float:
        return sum(t.amount_x_ebitda for t in self.debt.tranches)

    def revenue_growth_by_year(self) -> list[float]:
        return _per_year(self.operations.revenue_growth, self.exit.holding_period_years)

    def ebitda_margin_by_year(self) -> list[float]:
        return _per_year(self.operations.ebitda_margin, self.exit.holding_period_years)

    def with_multiples(self, entry_multiple: float, exit_multiple: float) -> DealConfig:
        """Copy of this deal with different entry/exit multiples (for sensitivities)."""
        data = self.model_dump()
        data["entry"]["entry_multiple"] = entry_multiple
        data["exit"]["exit_multiple"] = exit_multiple
        return parse_config(data)


def _per_year(value: float | list[float], years: int) -> list[float]:
    """Expand a single assumption to one value per year (lists pass through)."""
    return list(value) if isinstance(value, list) else [value] * years


def _format_validation_error(err: ValidationError) -> str:
    lines = []
    for e in err.errors():
        location = ".".join(str(part) for part in e["loc"]) or "<root>"
        lines.append(f"  - {location}: {e['msg']}")
    return "Invalid deal assumptions:\n" + "\n".join(lines)


def parse_config(data: dict) -> DealConfig:
    """Validate a dict of assumptions (as read from YAML) into a DealConfig."""
    try:
        return DealConfig.model_validate(data)
    except ValidationError as err:
        raise ConfigError(_format_validation_error(err)) from None


def load_config(path: str | Path) -> DealConfig:
    """Read and validate a YAML assumptions file."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Assumptions file not found: {path}") from None
    except yaml.YAMLError as err:
        raise ConfigError(f"Could not parse YAML in {path}: {err}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping of assumptions at the top level")
    return parse_config(data)
