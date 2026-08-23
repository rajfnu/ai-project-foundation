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
    existing_fields: Optional[dict] = None

    def ensure_project() -> Project:
        nonlocal project
        if project is None:
            project = client.find_project(owner, project_title(repo))
        if project is None:
            raise RuntimeError("field action planned without a project to attach to")
        return project

    def fields_by_name() -> dict:
        # Lazily list fields on the (now-existing) project. This is how we discover
        # GitHub's built-in fields — notably the auto-created single-select "Status" —
        # that the greenfield plan could not see because it ran before the project existed.
        nonlocal existing_fields
        if existing_fields is None:
            existing_fields = {f.name: f for f in client.list_fields(ensure_project().id)}
        return existing_fields

    for action in actions:
        if action.kind is GhActionKind.CREATE_PROJECT:
            project = client.create_project(action.data["owner"], action.data["title"])
            existing_fields = None  # re-list to pick up built-in fields
        elif action.kind is GhActionKind.CREATE_FIELD:
            p = ensure_project()
            fields = fields_by_name()
            name = action.data["name"]
            if name in fields:
                # field already exists (e.g. built-in Status): reconcile instead of recreating
                if action.data["data_type"] == "SINGLE_SELECT":
                    client.add_field_options(p.id, fields[name].id, action.data["options"])
            else:
                created = client.create_field(
                    p.id, name, action.data["data_type"], action.data["options"]
                )
                fields[name] = created
        elif action.kind is GhActionKind.ADD_FIELD_OPTIONS:
            p = ensure_project()
            client.add_field_options(p.id, action.data["field_id"], action.data["options"])
        elif action.kind is GhActionKind.CREATE_VIEW:
            p = ensure_project()
            view = client.create_view(p.id, action.data["name"], action.data["layout"])
            visible_ids = [
                fields_by_name()[n].id
                for n in action.data["visible_fields"]
                if n in fields_by_name()
            ]
            if action.data["filter"] or visible_ids:
                client.update_view(p.id, view.id, action.data["filter"], visible_ids)
        elif action.kind is GhActionKind.CREATE_LABEL:
            client.create_label(
                f"{owner}/{repo}",
                action.data["name"],
                action.data["color"],
                action.data["description"],
            )

    return project or client.find_project(owner, project_title(repo))
