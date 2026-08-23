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
    sync: "Optional[SyncReport]" = None

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

    # Project the current slice onto the board — but only once a real slice exists, so a
    # fresh greenfield setup doesn't leave an empty placeholder card.
    sync_report = None
    if github_enabled and client is not None and project is not None:
        status = _read_status_yml(root)
        if status.get("build_slice") or status.get("status"):
            sync_report = run_sync(root, client, owner, repo)

    return SetupReport(
        file_findings, github_findings, file_actions, github_actions,
        dry_run=False, applied=True, sync=sync_report,
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
        checks.append(Check("github_fields", "Project fields", _worst([f.status for f in field_statuses])))
        view_statuses = [v for k, v in gh_findings.items() if k.startswith("view:")]
        checks.append(Check("github_views", "Project views", _worst([f.status for f in view_statuses])))

    # invariant + snapshot
    status = _read_status_yml(root)
    checks.append(_independent_review_check(status))

    return HealthReport(checks=checks, snapshot=status)


# --- sync -----------------------------------------------------------------------------

# repository status key -> GitHub Project field name
_SYNC_FIELD_MAP = {
    "status": "Status",
    "build_slice": "Build / Slice",
    "current_actor": "Current Actor",
    "next_actor": "Next Actor",
    "review_status": "Review Status",
    "priority": "Priority",
    "customer_ready": "Customer Ready",
}


@dataclass
class SyncReport:
    item_title: str
    fields_set: dict
    created: bool


def _coerce_value(value) -> str:
    # YAML 1.1 parses No/Yes/Off/On as booleans; map back to the option names we use.
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def run_sync(root: Path, client: GitHubClient, owner: str, repo: str) -> SyncReport:
    """Push docs/status/current.yml into the current slice's Project item (one-way)."""
    from aip.standard import project_title

    status = _read_status_yml(root)
    project = client.find_project(owner, project_title(repo))
    if project is None:
        raise RuntimeError("no GitHub Project found — run `aip setup` first")

    fields = {f.name: f for f in client.list_fields(project.id)}
    title = status.get("build_slice") or "Current Slice"

    item = next((i for i in client.list_items(project.id) if i.title == title), None)
    created = False
    if item is None:
        item = client.add_draft_item(project.id, title)
        created = True

    fields_set: dict = {}
    for key, field_name in _SYNC_FIELD_MAP.items():
        value = status.get(key)
        if value is None:
            continue
        field_obj = fields.get(field_name)
        if field_obj is None:
            continue
        display = _coerce_value(value)
        client.set_field_value(project.id, item.id, field_obj, display)
        fields_set[field_name] = display

    return SyncReport(item_title=title, fields_set=fields_set, created=created)


def _worst(statuses: list[Status]) -> Status:
    if any(s is Status.MISSING for s in statuses):
        return Status.MISSING
    if any(s is Status.PARTIAL for s in statuses):
        return Status.PARTIAL
    return Status.PRESENT
