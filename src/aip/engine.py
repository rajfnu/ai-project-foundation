"""Orchestration: the audit -> plan -> (present) -> apply -> stamp -> verify pipeline.

Same engine for greenfield, brownfield, and re-runs — only the size of the plan differs.
The engine is the single place that ties the repository side and the GitHub side together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import re

import yaml

from aip import state as state_mod
from aip.apply import apply_actions
from aip.audit import Finding, Status, audit_files
from aip.github.apply import apply_github_actions
from aip.github.audit import audit_github
from aip.github.client import GitHubClient
from aip.github.plan import GhAction, plan_github_actions
from aip.plan import Action, plan_file_actions
from aip.standard import STANDARD_VERSION


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


# --- handoff (protocol transitions) ---------------------------------------------------

class InvariantError(RuntimeError):
    """Raised when a transition would violate the independent-review invariant."""


# Canonical events and the status changes each implies. Roles are structural: the
# Developer implements; the Reviewer (the architect/reviewer role) independently accepts.
_EVENT_TRANSITIONS = {
    "ACK": {"review_status": "ACK"},
    "GO": {"review_status": "GO", "implementer": "Developer",
           "current_actor": "Developer", "next_actor": "Reviewer"},
    "CHECK": {"review_status": "CHECK", "current_actor": "Developer", "next_actor": "Reviewer"},
    "FIX": {"review_status": "FIX", "current_actor": "Reviewer", "next_actor": "Developer"},
    "TECHNICALLY ACCEPTED": {"review_status": "TECHNICALLY ACCEPTED",
                             "current_actor": "Reviewer", "next_actor": "Human"},
}

_EVENT_ALIASES = {
    "ACCEPTED": "TECHNICALLY ACCEPTED",
    "TECHNICALLY-ACCEPTED": "TECHNICALLY ACCEPTED",
    "TECHNICALLY_ACCEPTED": "TECHNICALLY ACCEPTED",
}


@dataclass
class HandoffReport:
    record_path: str
    event: str
    review_status: str


def _normalize_event(event: str) -> str:
    key = " ".join(event.strip().upper().split())
    key = _EVENT_ALIASES.get(key.replace(" ", "-"), key)
    if key not in _EVENT_TRANSITIONS:
        valid = ", ".join(_EVENT_TRANSITIONS)
        raise ValueError(f"unknown event {event!r}; valid events: {valid}")
    return key


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return '"' + str(value).replace('"', '\\"') + '"'


def _update_status_yml(root: Path, updates: dict) -> None:
    path = root / "docs/status/current.yml"
    text = path.read_text() if path.is_file() else ""
    for key, value in updates.items():
        line = f"{key}: {_yaml_scalar(value)}"
        if re.search(rf"(?m)^{re.escape(key)}:.*$", text):
            text = re.sub(rf"(?m)^{re.escape(key)}:.*$", line, text)
        else:
            text = (text + ("" if text.endswith("\n") or text == "" else "\n")) + line + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_handoff(
    root: Path,
    event: str,
    by: Optional[str] = None,
    slice: Optional[str] = None,
    note: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> HandoffReport:
    ev = _normalize_event(event)
    status = _read_status_yml(root)

    updates = dict(_EVENT_TRANSITIONS[ev])
    if slice:
        updates["build_slice"] = slice

    if ev == "TECHNICALLY ACCEPTED":
        acceptor = by or "Reviewer"
        implementer = status.get("implementer")
        if implementer and acceptor == implementer:
            raise InvariantError(
                f"{acceptor} implemented this slice and cannot technically accept it. "
                "Independent review requires a different actor."
            )
        updates["acceptor"] = acceptor

    _update_status_yml(root, updates)

    ts = timestamp or _utc_timestamp()
    slice_name = slice or status.get("build_slice") or "Current Slice"
    slug = ev.lower().replace(" ", "-")
    handoffs_dir = root / "docs/handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    record_path = handoffs_dir / f"{ts}-{slug}.md"
    counter = 2
    while record_path.exists():  # avoid clobbering a same-second, same-event record
        record_path = handoffs_dir / f"{ts}-{slug}-{counter}.md"
        counter += 1
    record_path.write_text(
        f"# Handoff: {ev} — {slice_name}\n\n"
        f"- Event: {ev}\n"
        f"- Slice: {slice_name}\n"
        f"- By: {by or '-'}\n"
        f"- Timestamp: {ts}\n"
        f"- Resulting review status: {updates['review_status']}\n\n"
        f"## Note\n{note or '(none)'}\n"
    )
    return HandoffReport(str(record_path), ev, updates["review_status"])


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


# --- upgrade --------------------------------------------------------------------------

# Registry of standard migrations: version N -> a callable(root) that migrates a repo from
# version N-1 to N. Empty at standard version 1; future versions register their steps here.
MIGRATIONS: dict = {}


def migrations_to_run(current: int, target: int, registry: dict = MIGRATIONS) -> list:
    """Ordered list of migration versions to apply to go from `current` to `target`."""
    return sorted(v for v in registry if current < v <= target)


@dataclass
class UpgradeReport:
    from_version: int
    to_version: int
    applied: bool
    setup: SetupReport
    migrations_run: list

    @property
    def changed(self) -> bool:
        return self.from_version != self.to_version or self.setup.total_actions > 0


def run_upgrade(
    root: Path,
    client: Optional[GitHubClient],
    owner: str,
    repo: str,
    dry_run: bool,
    github_enabled: bool = True,
) -> UpgradeReport:
    from aip.config import read_config, set_standard_version

    current = read_config(root).standard_version
    target = STANDARD_VERSION
    pending = migrations_to_run(current, target)

    # Re-converge the standard (adds new files/fields/views, refreshes managed blocks).
    setup_report = run_setup(root, client, owner, repo, dry_run=dry_run, github_enabled=github_enabled)

    if dry_run:
        return UpgradeReport(current, target, applied=False, setup=setup_report, migrations_run=pending)

    for version in pending:
        MIGRATIONS[version](root)
    if current != target:
        set_standard_version(root, target)  # version of record lives in config

    return UpgradeReport(current, target, applied=True, setup=setup_report, migrations_run=pending)
