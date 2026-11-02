from __future__ import annotations

import copy
from pathlib import Path

import pytest

from lbo.config import DealConfig, load_config, parse_config

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "example.yaml"

# A deliberately tiny deal with round numbers, small enough to check by hand.
# See test_hand_case.py for the full manual calculation.
TINY_DEAL: dict = {
    "entry": {
        "ltm_revenue": 100.0,
        "ltm_ebitda": 20.0,
        "entry_multiple": 5.0,
        "transaction_fees_pct_ev": 0.02,
        "minimum_cash": 5.0,
    },
    "operations": {
        "revenue_growth": 0.10,
        "ebitda_margin": 0.20,
        "da_pct_revenue": 0.05,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue_change": 0.10,
        "tax_rate": 0.25,
    },
    "exit": {"holding_period_years": 2, "exit_multiple": 5.5},
    "debt": {
        "tranches": [
            {
                "name": "Senior",
                "amount_x_ebitda": 2.5,
                "interest_rate": 0.10,
                "mandatory_amortization_pct": 0.10,
                "sweep": True,
            }
        ],
        "cash_sweep_pct": 1.0,
    },
}


@pytest.fixture
def example_config() -> DealConfig:
    return load_config(EXAMPLE)


@pytest.fixture
def tiny_deal_dict() -> dict:
    return copy.deepcopy(TINY_DEAL)


@pytest.fixture
def tiny_config(tiny_deal_dict: dict) -> DealConfig:
    return parse_config(tiny_deal_dict)
