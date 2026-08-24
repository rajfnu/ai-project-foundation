from pathlib import Path

from typer.testing import CliRunner

from aip.bootstrap import BRIEF_PATH, ProjectAnswers, write_project_brief
from aip.cli import app
from aip.config import read_config, validate_config
from aip.engine import run_setup, run_upgrade
from aip.github.fake import FakeGitHub
from aip.standard import STANDARD_VERSION


runner = CliRunner()


FOUNDATION_FILES = (
    "CORE.md",
    "REQUIREMENTS.md",
    "ACCEPTANCE.md",
    "ARCHITECTURE.md",
    "PLAN.md",
    "CONSTRAINTS.md",
    "GUARDRAILS.md",
    "DECISIONS.md",
    "RUNBOOK.md",
)


def test_setup_creates_complete_v2_foundation(tmp_path: Path):
    run_setup(tmp_path, None, "", "", dry_run=False, github_enabled=False)

    for filename in FOUNDATION_FILES:
        assert (tmp_path / filename).is_file(), filename
    config = read_config(tmp_path)
    assert config.standard_version == STANDARD_VERSION
    assert validate_config(config) == []
    assert config.providers["openai"]["secret_ref"] == "env:OPENAI_API_KEY"


def test_init_records_ten_answers_without_credentials(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "init", "--path", str(tmp_path),
            "--name", "Widget", "--objective", "Reduce rework",
            "--users", "Operators", "--scope", "One workflow",
            "--out-of-scope", "Billing", "--stack", "Python",
            "--deployment", "Azure", "--data", "Confidential",
            "--quality", "Unit and end-to-end gates", "--approvals", "Deploy and delete",
        ],
    )

    assert result.exit_code == 0, result.stdout
    brief = (tmp_path / BRIEF_PATH).read_text()
    assert "Project Brief — Widget" in brief
    assert "Reduce rework" in brief
    assert "Deploy and delete" in brief
    assert "API_KEY" not in brief


def test_initialized_brief_is_never_overwritten(tmp_path: Path):
    answers = ProjectAnswers("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")
    write_project_brief(tmp_path, answers)

    try:
        write_project_brief(tmp_path, answers)
    except FileExistsError:
        pass
    else:
        raise AssertionError("initialized project brief was overwritten")


def test_inline_provider_secret_is_rejected(tmp_path: Path):
    run_setup(tmp_path, None, "", "", dry_run=False, github_enabled=False)
    path = tmp_path / ".aip/config.yml"
    path.write_text(path.read_text().replace(
        "openai:    { secret_ref: env:OPENAI_API_KEY }",
        "openai: { api_key: forbidden }",
    ))

    assert any("inline secret" in defect for defect in validate_config(read_config(tmp_path)))


def test_v1_upgrade_adds_v2_roles_and_provider_references(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    config_path = tmp_path / ".aip/config.yml"
    config_path.write_text("""standard_version: 1
roles:
  architect_reviewer: {agent: opus}
  developer: {agent: codex}
github: {project: true}
workflow: {independent_review_required: true}
""")

    run_upgrade(tmp_path, client, "acme", "widget", dry_run=False)

    config = read_config(tmp_path)
    assert config.standard_version == STANDARD_VERSION
    assert validate_config(config) == []
    assert config.roles["developer"]["agent"] == "codex"
