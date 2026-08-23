import hashlib
from pathlib import Path

import pytest

from aip.audit import Status
from aip.engine import run_health, run_setup
from aip.github.fake import FakeGitHub


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# --- Greenfield ----------------------------------------------------------------------

def test_greenfield_setup_establishes_standard(tmp_path: Path):
    client = FakeGitHub("acme", "widget")

    report = run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    assert report.applied
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".aip/config.yml").exists()
    assert client.find_project("acme", "AIP · widget") is not None
    # a follow-up audit is clean
    assert run_health(tmp_path, client, "acme", "widget").compliant


# --- Dry run (brownfield safety) -----------------------------------------------------

def test_dry_run_makes_zero_mutations(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# human owned\n")
    client = FakeGitHub("acme", "widget")
    before_fs = snapshot(tmp_path)
    before_projects = len(client.projects_for("acme"))

    report = run_setup(tmp_path, client, "acme", "widget", dry_run=True)

    assert not report.applied
    assert report.total_actions > 0  # there IS work proposed
    assert snapshot(tmp_path) == before_fs  # but nothing changed on disk
    assert len(client.projects_for("acme")) == before_projects  # nor on github


# --- Idempotency ---------------------------------------------------------------------

def test_second_setup_reports_already_compliant(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    second = run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    assert second.total_actions == 0
    assert second.already_compliant
    assert len(client.projects_for("acme")) == 1


# --- Health --------------------------------------------------------------------------

def test_health_on_fresh_repo_is_non_compliant(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    health = run_health(tmp_path, client, "acme", "widget")
    assert not health.compliant
    assert any(c.status is Status.MISSING for c in health.checks)


def test_health_identifies_self_acceptance_invariant_violation(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    # a slice technically accepted by its own implementer violates the invariant
    (tmp_path / "docs/status/current.yml").write_text(
        "review_status: TECHNICALLY ACCEPTED\n"
        "implementer: Developer\n"
        "acceptor: Developer\n"
        "build_slice: Build 005A\n"
        "current_actor: Developer\n"
        "next_actor: Reviewer\n"
        "open_human_decisions: []\n"
    )

    health = run_health(tmp_path, client, "acme", "widget")

    inv = next(c for c in health.checks if c.key == "independent_review")
    assert inv.status is Status.MISSING  # FAIL
    assert not health.compliant


def test_health_snapshot_reads_status_yml(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    (tmp_path / "docs/status/current.yml").write_text(
        "review_status: CHECK\n"
        "implementer: Developer\n"
        "acceptor: null\n"
        "build_slice: Build 005A\n"
        "current_actor: Developer\n"
        "next_actor: Architect\n"
        "open_human_decisions:\n  - should we ship?\n"
    )

    health = run_health(tmp_path, client, "acme", "widget")

    assert health.snapshot["build_slice"] == "Build 005A"
    assert health.snapshot["current_actor"] == "Developer"
    assert health.open_human_decisions == 1
