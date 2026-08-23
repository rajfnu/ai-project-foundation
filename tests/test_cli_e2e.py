from pathlib import Path

from typer.testing import CliRunner

from aip.cli import app

runner = CliRunner()


def test_setup_dry_run_no_github_changes_nothing(tmp_path: Path):
    result = runner.invoke(app, ["setup", "--no-github", "--dry-run", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Proposed changes" in result.stdout
    assert not (tmp_path / "AGENTS.md").exists()


def test_setup_apply_no_github_creates_files(tmp_path: Path):
    result = runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".aip/config.yml").exists()


def test_second_setup_reports_already_compliant(tmp_path: Path):
    runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])
    result = runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Already compliant" in result.stdout


def test_health_exit_codes(tmp_path: Path):
    fresh = runner.invoke(app, ["health", "--no-github", "--path", str(tmp_path)])
    assert fresh.exit_code == 1
    assert "NON-COMPLIANT" in fresh.stdout

    runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])
    healthy = runner.invoke(app, ["health", "--no-github", "--path", str(tmp_path)])
    assert healthy.exit_code == 0
    assert "COMPLIANT" in healthy.stdout


def test_handoff_cli_records_and_enforces_invariant(tmp_path: Path):
    runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])

    go = runner.invoke(app, ["handoff", "GO", "--slice", "B1", "--path", str(tmp_path)])
    assert go.exit_code == 0 and "GO" in go.stdout
    assert list((tmp_path / "docs/handoffs").glob("*.md"))

    # self-acceptance refused
    bad = runner.invoke(app, ["handoff", "TECHNICALLY-ACCEPTED", "--by", "Developer", "--path", str(tmp_path)])
    assert bad.exit_code == 2

    # independent acceptance ok
    ok = runner.invoke(app, ["handoff", "ACCEPTED", "--by", "Reviewer", "--path", str(tmp_path)])
    assert ok.exit_code == 0

    bogus = runner.invoke(app, ["handoff", "NOPE", "--path", str(tmp_path)])
    assert bogus.exit_code == 2


def test_upgrade_cli_bumps_version(tmp_path: Path):
    runner.invoke(app, ["setup", "--no-github", "--yes", "--path", str(tmp_path)])
    import re
    cfg = tmp_path / ".aip/config.yml"
    cfg.write_text(re.sub(r"(?m)^standard_version:.*$", "standard_version: 0", cfg.read_text()))

    result = runner.invoke(app, ["upgrade", "--no-github", "--yes", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Upgraded to standard version" in result.stdout

    again = runner.invoke(app, ["upgrade", "--no-github", "--yes", "--path", str(tmp_path)])
    assert "Already at standard version" in again.stdout
