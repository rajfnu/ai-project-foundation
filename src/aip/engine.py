"""Orchestration: the audit -> plan -> (present) -> apply -> stamp -> verify pipeline.

Same engine for greenfield, brownfield, and re-runs — only the size of the plan differs.
The engine is the single place that ties the repository side and the GitHub side together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from aip import state as state_mod
from aip.apply import apply_actions
from aip.audit import Finding, Status, audit_files
from aip.github.apply import apply_github_actions
from aip.github.audit import audit_github
from aip.github.client import GitHubClient
from aip.github.plan import GhAction, plan_github_actions
from aip.plan import Action, plan_file_actions


# --- setup ---------------------------------------------------------------------------

@dataclass
class SetupReport:
    file_findings: list[Finding]
    github_findings: list[Finding]
    file_actions: list[Action]
    github_actions: list[GhAction]
    dry_run: bool
    applied: bool

    @property
    def total_actions(self) -> int:
        return len(self.file_actions) + len(self.github_actions)

    @property
    def already_compliant(self) -> bool:
        return self.total_actions == 0


def run_setup(
    root: Path,
    client: Optional[GitHubClient],
    owner: str,
    repo: str,
    dry_run: bool,
    github_enabled: bool = True,
) -> SetupReport:
    file_findings = audit_files(root)
    file_actions = plan_file_actions(root)

    if github_enabled and client is not None:
        github_findings = audit_github(client, owner, repo)
        github_actions = plan_github_actions(client, owner, repo)
    else:
        github_findings, github_actions = [], []

    if dry_run:
        return SetupReport(
            file_findings, github_findings, file_actions, github_actions,
            dry_run=True, applied=False,
        )

    apply_actions(root, file_actions)
    project = None
    if github_enabled and client is not None:
        project = apply_github_actions(client, owner, repo, github_actions)
    # stamp the resolved project into state (idempotent)
    state_mod.write_project(root, project)

    return SetupReport(
        file_findings, github_findings, file_actions, github_actions,
        dry_run=False, applied=True,
    )


# --- health --------------------------------------------------------------------------

@dataclass
class Check:
    key: str
    label: str
    status: Status
    detail: str = ""


@dataclass
class HealthReport:
    checks: list[Check]
    snapshot: dict = field(default_factory=dict)

    @property
    def compliant(self) -> bool:
        return all(c.status is Status.PRESENT for c in self.checks)

    @property
    def open_human_decisions(self) -> int:
        decisions = self.snapshot.get("open_human_decisions") or []
        return len(decisions)


def _read_status_yml(root: Path) -> dict:
    path = root / "docs/status/current.yml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _independent_review_check(status: dict) -> Check:
    review = status.get("review_status")
    implementer = status.get("implementer")
    acceptor = status.get("acceptor")
    if (
        review == "TECHNICALLY ACCEPTED"
        and implementer is not None
        and acceptor is not None
        and implementer == acceptor
    ):
        return Check(
            "independent_review",
            "Independent review",
            Status.MISSING,
            "slice accepted by its own implementer — invariant violated",
        )
    return Check("independent_review", "Independent review", Status.PRESENT)


def run_health(
    root: Path,
    client: Optional[GitHubClient],
    owner: str,
    repo: str,
    github_enabled: bool = True,
) -> HealthReport:
    checks: list[Check] = []

    # repository files
    file_findings = audit_files(root)
    missing_files = [f for f in file_findings if f.status is not Status.PRESENT]
    checks.append(
        Check(
            "repository",
            "Repository",
            Status.PRESENT if not missing_files else Status.MISSING,
            "" if not missing_files else f"{len(missing_files)} missing",
        )
    )
    # key documents surfaced individually
    by_key = {f.key: f for f in file_findings}
    for key, label in [
        ("AGENTS.md", "AGENTS.md"),
        ("CLAUDE.md", "CLAUDE.md"),
        ("docs/status/current.yml", "Current status"),
    ]:
        checks.append(Check(key, label, by_key[key].status, by_key[key].detail))

    # github
    if github_enabled and client is not None:
        gh_findings = {f.key: f for f in audit_github(client, owner, repo)}
        checks.append(
            Check(
                "github_project",
                "GitHub Project",
                gh_findings["github_project"].status,
                gh_findings["github_project"].detail,
            )
        )
        field_statuses = [v for k, v in gh_findings.items() if k.startswith("field:")]
        worst = _worst([f.status for f in field_statuses])
        checks.append(Check("github_fields", "Project fields", worst))

    # invariant + snapshot
    status = _read_status_yml(root)
    checks.append(_independent_review_check(status))

    return HealthReport(checks=checks, snapshot=status)


def _worst(statuses: list[Status]) -> Status:
    if any(s is Status.MISSING for s in statuses):
        return Status.MISSING
    if any(s is Status.PARTIAL for s in statuses):
        return Status.PARTIAL
    return Status.PRESENT
