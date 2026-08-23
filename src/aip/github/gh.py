"""Real GitHub client that shells out to the `gh` CLI (and `gh api graphql` where needed).

The subprocess runner is injectable so command construction can be tested without touching
the network. Only the applier calls the mutating methods, and only after the planner has
confirmed the target is missing — so every call here is part of an idempotent converge.
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable, Optional

from aip.github.client import Field, Project

Runner = Callable[[list[str], Optional[str]], str]


def _default_runner(args: list[str], stdin: Optional[str]) -> str:
    proc = subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


class GhGitHub:
    def __init__(self, runner: Optional[Runner] = None):
        self._run = runner or _default_runner

    # --- read ---
    def find_project(self, owner: str, title: str) -> Optional[Project]:
        out = self._run(
            ["gh", "project", "list", "--owner", owner, "--format", "json", "--limit", "200"],
            None,
        )
        data = json.loads(out or "{}")
        for p in data.get("projects", []):
            if p.get("title") == title:
                return Project(id=p["id"], number=p["number"], title=p["title"])
        return None

    def list_fields(self, project_id: str) -> list[Field]:
        # gh project field-list works by number+owner; we fetch via graphql for id-based access
        query = (
            "query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{"
            "... on ProjectV2FieldCommon{id name dataType} "
            "... on ProjectV2SingleSelectField{options{name}}}}}}}"
        )
        out = self._run(
            ["gh", "api", "graphql", "-f", f"query={query}", "-F", f"id={project_id}"], None
        )
        data = json.loads(out)
        nodes = data["data"]["node"]["fields"]["nodes"]
        fields: list[Field] = []
        for n in nodes:
            if not n:
                continue
            options = [o["name"] for o in n.get("options", [])]
            fields.append(Field(id=n["id"], name=n["name"], data_type=n["dataType"], options=options))
        return fields

    def list_labels(self, repo: str) -> list[str]:
        out = self._run(
            ["gh", "label", "list", "--repo", repo, "--json", "name", "--limit", "500"], None
        )
        data = json.loads(out or "[]")
        return [item["name"] for item in data]

    # --- write ---
    def create_project(self, owner: str, title: str) -> Project:
        out = self._run(
            ["gh", "project", "create", "--owner", owner, "--title", title, "--format", "json"],
            None,
        )
        p = json.loads(out)
        return Project(id=p["id"], number=p["number"], title=p["title"])

    def create_field(
        self, project_id: str, name: str, data_type: str, options: list[str]
    ) -> Field:
        query = (
            "mutation($p:ID!,$n:String!,$t:ProjectV2CustomFieldType!,$o:[ProjectV2SingleSelectFieldOptionInput!]){"
            "createProjectV2Field(input:{projectId:$p,name:$n,dataType:$t,singleSelectOptions:$o}){"
            "projectV2Field{... on ProjectV2FieldCommon{id name dataType}}}}"
        )
        args = [
            "gh", "api", "graphql", "-f", f"query={query}",
            "-F", f"p={project_id}", "-f", f"n={name}", "-f", f"t={data_type}",
        ]
        opts_json = json.dumps(
            [{"name": o, "color": "GRAY", "description": ""} for o in options]
        )
        args += ["-f", f"o={opts_json}"] if data_type == "SINGLE_SELECT" else []
        out = self._run(args, None)
        node = json.loads(out)["data"]["createProjectV2Field"]["projectV2Field"]
        return Field(id=node["id"], name=node["name"], data_type=node["dataType"], options=list(options))

    def add_field_options(self, project_id: str, field_id: str, options: list[str]) -> Field:
        # gh/GraphQL cannot append options to an existing single-select field in one supported
        # call; document honestly and surface for manual follow-up rather than fake success.
        raise NotImplementedError(
            "Appending options to an existing single-select field is not supported by the GitHub "
            "API via gh. Add these options once in the Project UI: " + ", ".join(options)
        )

    def create_label(self, repo: str, name: str, color: str, description: str) -> None:
        self._run(
            [
                "gh", "label", "create", name, "--repo", repo,
                "--color", color, "--description", description, "--force",
            ],
            None,
        )
