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
