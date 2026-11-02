from __future__ import annotations

import pytest

from lbo.config import parse_config
from lbo.deal import run_deal


def test_bridge_sums_to_total_gain_example(example_config):
    b = run_deal(example_config).bridge
    assert b.sum_of_components == pytest.approx(b.total_gain, abs=1e-9)


def test_ebitda_growth_split_is_exact(example_config):
    result = run_deal(example_config)
    b = result.bridge
    entry_ebitda = example_config.entry.ltm_ebitda
    exit_ebitda = result.operations[-1].ebitda
    expected = (exit_ebitda - entry_ebitda) * example_config.entry.entry_multiple
    assert b.ebitda_growth == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("exit_multiple", [4.0, 5.0, 7.5])
@pytest.mark.parametrize("margin", [0.15, 0.20, 0.30])
def test_bridge_sums_with_multiple_contraction_and_margin_changes(
    tiny_deal_dict, exit_multiple, margin
):
    tiny_deal_dict["exit"]["exit_multiple"] = exit_multiple
    tiny_deal_dict["operations"]["ebitda_margin"] = margin
    b = run_deal(parse_config(tiny_deal_dict)).bridge
    assert b.sum_of_components == pytest.approx(b.total_gain, abs=1e-9)


def test_no_multiple_expansion_when_exit_equals_entry(example_config):
    assert example_config.exit.exit_multiple == example_config.entry.entry_multiple
    assert run_deal(example_config).bridge.multiple_expansion == pytest.approx(0.0)
