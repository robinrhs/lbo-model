from __future__ import annotations

import pytest

from lbo.transaction import build_sources_and_uses


def test_sources_equal_uses(example_config):
    su = build_sources_and_uses(example_config)
    assert su.total_sources == pytest.approx(su.total_uses, abs=1e-9)


def test_example_sources_and_uses(example_config):
    su = build_sources_and_uses(example_config)
    # 40 EBITDA x 10.0x = 400 EV; 2.5% fees = 10; minimum cash 10
    assert su.total_uses == pytest.approx(420.0)
    # 3.0x + 1.5x of 40 EBITDA = 180 debt -> equity plug 240
    assert su.total_debt == pytest.approx(180.0)
    assert su.sponsor_equity == pytest.approx(240.0)
    assert list(su.debt) == ["Senior Term Loan", "Subordinated Notes"]
