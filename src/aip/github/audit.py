"""Audit the GitHub side against the standard. Read-only."""

from __future__ import annotations

from aip.audit import Finding, Status
from aip.github.client import GitHubClient
from aip.standard import REQUIRED_FIELDS, REQUIRED_LABELS, REQUIRED_VIEWS, project_title


def audit_github(client: GitHubClient, owner: str, repo: str) -> list[Finding]:
    findings: list[Finding] = []
    project = client.find_project(owner, project_title(repo))

    if project is None:
        findings.append(
            Finding("github_project", "GitHub Project", Status.MISSING, "no matching project")
        )
        # fields and views can't exist without a project
        for spec in REQUIRED_FIELDS:
            findings.append(Finding(f"field:{spec.name}", f"Field: {spec.name}", Status.MISSING))
        for view in REQUIRED_VIEWS:
            findings.append(Finding(f"view:{view.name}", f"View: {view.name}", Status.MISSING))
        findings.append(_labels_finding(client, owner, repo))
        return findings

    findings.append(
        Finding("github_project", "GitHub Project", Status.PRESENT, f"#{project.number}")
    )
    existing = {f.name: f for f in client.list_fields(project.id)}
    for spec in REQUIRED_FIELDS:
        field = existing.get(spec.name)
        if field is None:
            findings.append(Finding(f"field:{spec.name}", f"Field: {spec.name}", Status.MISSING))
        elif spec.data_type == "SINGLE_SELECT" and any(
            o not in field.options for o in spec.options
        ):
            missing = [o for o in spec.options if o not in field.options]
            findings.append(
                Finding(
                    f"field:{spec.name}",
                    f"Field: {spec.name}",
                    Status.PARTIAL,
                    f"missing options: {', '.join(missing)}",
                )
            )
        else:
            findings.append(Finding(f"field:{spec.name}", f"Field: {spec.name}", Status.PRESENT))

    existing_views = {v.name for v in client.list_views(project.id)}
    for view in REQUIRED_VIEWS:
        status = Status.PRESENT if view.name in existing_views else Status.MISSING
        findings.append(Finding(f"view:{view.name}", f"View: {view.name}", status))

    findings.append(_labels_finding(client, owner, repo))
    return findings


def _labels_finding(client: GitHubClient, owner: str, repo: str) -> Finding:
    existing = set(client.list_labels(f"{owner}/{repo}"))
    required = {label.name for label in REQUIRED_LABELS}
    have = required & existing
    if have == required:
        status = Status.PRESENT
        detail = ""
    elif have:
        status = Status.PARTIAL
        detail = f"missing: {', '.join(sorted(required - have))}"
    else:
        status = Status.MISSING
        detail = ""
    return Finding("labels", "Labels", status, detail)
