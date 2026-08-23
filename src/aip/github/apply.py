"""Apply GitHub-side actions via the client. Additive and idempotent."""

from __future__ import annotations

from typing import Optional

from aip.github.client import GitHubClient, Project
from aip.github.plan import GhAction, GhActionKind
from aip.standard import project_title


def apply_github_actions(
    client: GitHubClient, owner: str, repo: str, actions: list[GhAction]
) -> Optional[Project]:
    """Execute actions. Returns the resulting Project (created or adopted), if any."""
    project: Optional[Project] = client.find_project(owner, project_title(repo))

    def ensure_project() -> Project:
        nonlocal project
        if project is None:
            project = client.find_project(owner, project_title(repo))
        if project is None:
            raise RuntimeError("field action planned without a project to attach to")
        return project

    for action in actions:
        if action.kind is GhActionKind.CREATE_PROJECT:
            project = client.create_project(action.data["owner"], action.data["title"])
        elif action.kind is GhActionKind.CREATE_FIELD:
            p = ensure_project()
            client.create_field(
                p.id, action.data["name"], action.data["data_type"], action.data["options"]
            )
        elif action.kind is GhActionKind.ADD_FIELD_OPTIONS:
            p = ensure_project()
            client.add_field_options(p.id, action.data["field_id"], action.data["options"])
        elif action.kind is GhActionKind.CREATE_LABEL:
            client.create_label(
                f"{owner}/{repo}",
                action.data["name"],
                action.data["color"],
                action.data["description"],
            )

    return project or client.find_project(owner, project_title(repo))
