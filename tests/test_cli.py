from typer.testing import CliRunner

from aip import __version__
from aip.cli import app
from aip.standard import STANDARD_VERSION

runner = CliRunner()


def test_version_reports_cli_and_standard_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert f"standard {STANDARD_VERSION}" in result.stdout


def test_help_lists_setup_and_health():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "setup" in result.stdout
    assert "health" in result.stdout
