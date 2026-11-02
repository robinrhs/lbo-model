from __future__ import annotations

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
