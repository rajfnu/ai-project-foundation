"""Plan GitHub-side actions. Read-only; produces idempotent, additive actions."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field as dc_field
from typing import Optional

from aip.github.client import GitHubClient
from aip.standard import REQUIRED_FIELDS, REQUIRED_LABELS, project_title


class GhActionKind(enum.Enum):
    CREATE_PROJECT = "create GitHub Project"
    CREATE_FIELD = "create Project field"
    ADD_FIELD_OPTIONS = "add options to Project field"
    CREATE_LABEL = "create label"


@dataclass(frozen=True)
class GhAction:
    kind: GhActionKind
    target: str
    reason: str
    data: dict = dc_field(default_factory=dict)


def plan_github_actions(client: GitHubClient, owner: str, repo: str) -> list[GhAction]:
    actions: list[GhAction] = []
    project = client.find_project(owner, project_title(repo))

    if project is None:
        actions.append(
            GhAction(
                GhActionKind.CREATE_PROJECT,
                project_title(repo),
                reason="no matching project",
                data={"owner": owner, "title": project_title(repo)},
            )
        )
        existing_fields: dict[str, object] = {}
    else:
        existing_fields = {f.name: f for f in client.list_fields(project.id)}

    for spec in REQUIRED_FIELDS:
        field = existing_fields.get(spec.name)
        if field is None:
            actions.append(
                GhAction(
                    GhActionKind.CREATE_FIELD,
                    spec.name,
                    reason="missing field",
                    data={
                        "name": spec.name,
                        "data_type": spec.data_type,
                        "options": list(spec.options),
                    },
                )
            )
        elif spec.data_type == "SINGLE_SELECT":
            missing = [o for o in spec.options if o not in field.options]  # type: ignore[attr-defined]
            if missing:
                actions.append(
                    GhAction(
                        GhActionKind.ADD_FIELD_OPTIONS,
                        spec.name,
                        reason=f"missing options: {', '.join(missing)}",
                        # pass the FULL desired set so the applier can safely reconcile
                        # even when a required name collides with a GitHub default option.
                        data={"field_id": field.id, "options": list(spec.options)},  # type: ignore[attr-defined]
                    )
                )

    existing_labels = set(client.list_labels(f"{owner}/{repo}"))
    for label in REQUIRED_LABELS:
        if label.name not in existing_labels:
            actions.append(
                GhAction(
                    GhActionKind.CREATE_LABEL,
                    label.name,
                    reason="missing label",
                    data={
                        "name": label.name,
                        "color": label.color,
                        "description": label.description,
                    },
                )
            )

    return actions
