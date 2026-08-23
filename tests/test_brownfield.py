"""Realistic brownfield adoption: an existing, half-built project.

Proves the safety guarantees together: application code and human-authored docs survive,
an existing Project is adopted (not recreated), and only missing fields/labels/files are added.
"""

import hashlib
from pathlib import Path

from aip.engine import run_health, run_setup
from aip.github.fake import FakeGitHub
from aip.standard import REQUIRED_FIELDS, project_title


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_brownfield(tmp_path: Path) -> Path:
    # existing application code + git-like history stand-ins
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('the real app')\n")
    (tmp_path / "README.md").write_text("# Widget\nHalf-built product.\n")
    # a human-authored AGENTS.md WITHOUT the aip block
    (tmp_path / "AGENTS.md").write_text("# Team rules\n\nReview everything twice.\n")
    return tmp_path


def make_partial_github() -> FakeGitHub:
    client = FakeGitHub("acme", "widget", labels=["bug", "aip:blocked"])
    # a Project already exists with its (built-in) Status field fully reconciled
    project = client.create_project("acme", project_title("widget"))
    status = next(f for f in REQUIRED_FIELDS if f.name == "Status")
    client.set_field_options(project.id, status.name, status.options)
    return client


def test_brownfield_dry_run_preserves_everything(tmp_path: Path):
    root = make_brownfield(tmp_path)
    client = make_partial_github()
    app_before = _digest(root / "src" / "main.py")
    agents_before = _digest(root / "AGENTS.md")

    report = run_setup(root, client, "acme", "widget", dry_run=True)

    assert report.total_actions > 0
    # nothing created for what already exists
    assert not any(a.target == project_title("widget") for a in report.github_actions)
    assert not any(a.data.get("name") == "Status" for a in report.github_actions)
    assert not any(a.data.get("name") == "aip:blocked" for a in report.github_actions)
    # zero mutation
    assert _digest(root / "src" / "main.py") == app_before
    assert _digest(root / "AGENTS.md") == agents_before
    assert len(client.projects_for("acme")) == 1


def test_brownfield_apply_adds_only_missing_and_preserves(tmp_path: Path):
    root = make_brownfield(tmp_path)
    client = make_partial_github()
    app_before = _digest(root / "src" / "main.py")

    run_setup(root, client, "acme", "widget", dry_run=False)

    # app code untouched
    assert _digest(root / "src" / "main.py") == app_before
    # human AGENTS.md content preserved, aip block appended
    agents = (root / "AGENTS.md").read_text()
    assert "Review everything twice." in agents and "AIP:BEGIN" in agents
    # existing project adopted, not duplicated
    assert len(client.projects_for("acme")) == 1
    # all required fields now present; existing "Status" not duplicated
    project = client.find_project("acme", project_title("widget"))
    names = [f.name for f in client.list_fields(project.id)]
    assert names.count("Status") == 1
    assert set(names) == {f.name for f in REQUIRED_FIELDS}
    # now healthy
    assert run_health(root, client, "acme", "widget").compliant


def test_brownfield_is_idempotent(tmp_path: Path):
    root = make_brownfield(tmp_path)
    client = make_partial_github()
    run_setup(root, client, "acme", "widget", dry_run=False)

    second = run_setup(root, client, "acme", "widget", dry_run=False)
    assert second.already_compliant
    assert len(client.projects_for("acme")) == 1
