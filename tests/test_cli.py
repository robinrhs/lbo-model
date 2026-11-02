from __future__ import annotations

import yaml
from conftest import EXAMPLE

from lbo.cli import main


def test_cli_prints_summary(capsys):
    assert main(["run", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    for heading in ("Sources & Uses", "Returns", "Value creation bridge", "IRR sensitivity"):
        assert heading in out


def test_cli_exports_excel(tmp_path, capsys):
    target = tmp_path / "lbo.xlsx"
    assert main(["run", str(EXAMPLE), "--excel", str(target)]) == 0
    assert target.exists()


def test_cli_reports_config_errors(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("entry: {ltm_revenue: -1}\n", encoding="utf-8")
    assert main(["run", str(bad)]) == 1
    assert "Invalid deal assumptions" in capsys.readouterr().out


def test_cli_handles_total_loss(tmp_path, capsys):
    text = EXAMPLE.read_text(encoding="utf-8").replace("exit_multiple: 10.0", "exit_multiple: 1.0")
    wiped = tmp_path / "wiped.yaml"
    wiped.write_text(text, encoding="utf-8")
    assert main(["run", str(wiped), "--excel", str(tmp_path / "wiped.xlsx")]) == 0
    out = capsys.readouterr().out
    assert "0.00x" in out
    assert "-100.0%" in out
    assert "equity wiped out" in out


def test_cli_runs_deal_with_irr_below_minus_99_percent(tmp_path, capsys, tiny_deal_dict):
    # One-year tiny deal exiting at 1.7x: IRR = 0.025 / 57 - 1 = -99.96%
    # (see test_returns.py). This used to stop with "IRR not bracketed".
    tiny_deal_dict["exit"] = {"holding_period_years": 1, "exit_multiple": 1.7}
    path = tmp_path / "near_loss.yaml"
    path.write_text(yaml.safe_dump(tiny_deal_dict), encoding="utf-8")
    assert main(["run", str(path)]) == 0
    out = capsys.readouterr().out
    irr_line = next(line for line in out.splitlines() if "IRR (1-year hold)" in line)
    assert "-100.0%" in irr_line  # -99.96% rounds to -100.0% at one decimal
    assert "IRR not bracketed" not in out
