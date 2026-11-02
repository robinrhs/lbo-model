"""Public entry point: base case plus sensitivity table."""

from __future__ import annotations

from dataclasses import dataclass

from lbo.config import DealConfig
from lbo.deal import DealResult, run_deal
from lbo.sensitivity import SensitivityTable, build_sensitivity


@dataclass(frozen=True)
class LBOResult:
    base: DealResult
    sensitivity: SensitivityTable


def run_model(config: DealConfig) -> LBOResult:
    return LBOResult(base=run_deal(config), sensitivity=build_sensitivity(config))
