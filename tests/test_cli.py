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


def test_cli_handles_total_loss(tmp_path, capsys):
    text = EXAMPLE.read_text(encoding="utf-8").replace("exit_multiple: 10.0", "exit_multiple: 1.0")
    wiped = tmp_path / "wiped.yaml"
    wiped.write_text(text, encoding="utf-8")
    assert main(["run", str(wiped), "--excel", str(tmp_path / "wiped.xlsx")]) == 0
    out = capsys.readouterr().out
    assert "0.00x" in out
    assert "-100.0%" in out
    assert "equity wiped out" in out
