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


def test_share_of_gain_only_for_positive_gain(example_config):
    b = run_deal(example_config).bridge
    assert b.share_of_gain(b.total_gain) == pytest.approx(1.0)
    assert b.share_of_gain(b.revenue_growth) > 0

    losing = run_deal(example_config.with_multiples(10.0, 2.0)).bridge
    assert losing.total_gain < 0
    # Dividing by a loss would flip signs, so no share is reported.
    assert losing.share_of_gain(losing.revenue_growth) is None
    assert losing.share_of_gain(losing.total_gain) is None
