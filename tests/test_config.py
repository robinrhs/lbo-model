from __future__ import annotations

import pytest

from lbo.config import ConfigError, load_config, parse_config


def test_example_config_loads(example_config):
    assert example_config.exit.holding_period_years == 5
    assert len(example_config.revenue_growth_by_year()) == 5
    assert example_config.entry_ev == pytest.approx(400.0)


def test_scalar_assumption_is_broadcast(tiny_config):
    assert tiny_config.revenue_growth_by_year() == [0.10, 0.10]
    assert tiny_config.ebitda_margin_by_year() == [0.20, 0.20]


def test_unknown_key_is_rejected(tiny_deal_dict):
    tiny_deal_dict["exit"]["exit_multple"] = 6.0  # typo
    with pytest.raises(ConfigError, match=r"exit\.exit_multple"):
        parse_config(tiny_deal_dict)


def test_negative_multiple_is_rejected(tiny_deal_dict):
    tiny_deal_dict["entry"]["entry_multiple"] = -1.0
    with pytest.raises(ConfigError, match=r"entry\.entry_multiple"):
        parse_config(tiny_deal_dict)


def test_list_length_must_match_holding_period(tiny_deal_dict):
    tiny_deal_dict["operations"]["revenue_growth"] = [0.05, 0.05, 0.05]
    with pytest.raises(ConfigError, match="revenue_growth has 3 values"):
        parse_config(tiny_deal_dict)


def test_debt_above_uses_is_rejected(tiny_deal_dict):
    tiny_deal_dict["debt"]["tranches"][0]["amount_x_ebitda"] = 6.0  # 120 > uses of 107
    with pytest.raises(ConfigError, match="sponsor equity would be zero or negative"):
        parse_config(tiny_deal_dict)


def test_duplicate_tranche_names_are_rejected(tiny_deal_dict):
    tranche = tiny_deal_dict["debt"]["tranches"][0]
    tiny_deal_dict["debt"]["tranches"] = [tranche, dict(tranche)]
    with pytest.raises(ConfigError, match="unique"):
        parse_config(tiny_deal_dict)


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")
