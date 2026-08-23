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
            ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"id={project_id}"], None
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
        # gh cannot bind a list-of-objects GraphQL variable via -f/-F, so the single-select
        # options are inlined as GraphQL literals. Values come from the trusted standard;
        # names are JSON-escaped (valid GraphQL string escaping for our characters).
        result = "projectV2Field{... on ProjectV2FieldCommon{id name dataType}}"
        if data_type == "SINGLE_SELECT":
            literals = ", ".join(
                f'{{name: {json.dumps(o)}, color: GRAY, description: ""}}' for o in options
            )
            query = (
                "mutation($p:ID!,$n:String!){createProjectV2Field(input:{"
                "projectId:$p,name:$n,dataType:SINGLE_SELECT,"
                f"singleSelectOptions:[{literals}]}}){{{result}}}}}"
            )
            args = ["gh", "api", "graphql", "-f", f"query={query}",
                    "-f", f"p={project_id}", "-f", f"n={name}"]
        else:
            query = (
                "mutation($p:ID!,$n:String!,$t:ProjectV2CustomFieldType!){"
                "createProjectV2Field(input:{projectId:$p,name:$n,dataType:$t}){"
                f"{result}}}}}"
            )
            args = ["gh", "api", "graphql", "-f", f"query={query}",
                    "-f", f"p={project_id}", "-f", f"n={name}", "-f", f"t={data_type}"]
        out = self._run(args, None)
        node = json.loads(out)["data"]["createProjectV2Field"]["projectV2Field"]
        return Field(id=node["id"], name=node["name"], data_type=node["dataType"], options=list(options))

    # GitHub creates this exact single-select set on every new Project v2's built-in Status
    # field. When we find precisely these, it is safe to replace them on a fresh project.
    _GH_DEFAULT_STATUS = {"Todo", "In Progress", "Done"}

    def _single_select_options(self, project_id: str, field_id: str) -> list[tuple[str, str]]:
        query = (
            "query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{"
            "... on ProjectV2FieldCommon{id} "
            "... on ProjectV2SingleSelectField{id options{name color}}}}}}}"
        )
        out = self._run(
            ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"id={project_id}"], None
        )
        nodes = json.loads(out)["data"]["node"]["fields"]["nodes"]
        for n in nodes:
            if n and n.get("id") == field_id:
                return [(o["name"], o.get("color", "GRAY")) for o in n.get("options", [])]
        return []

    def add_field_options(self, project_id: str, field_id: str, options: list[str]) -> Field:
        """Add the given option names to an existing single-select field.

        updateProjectV2Field replaces the full option list (matching by name preserves
        existing options' item associations). To stay safe:
        - if the field holds exactly GitHub's default Status set, replace it outright
          (a fresh project — nothing is in use);
        - otherwise union existing options with the new ones so nothing is destroyed.
        """
        existing = self._single_select_options(project_id, field_id)
        existing_names = [n for n, _ in existing]

        if set(existing_names) == self._GH_DEFAULT_STATUS:
            base: list[tuple[str, str]] = []
        else:
            base = existing

        final = list(base)
        have = {n for n, _ in final}
        for name in options:
            if name not in have:
                final.append((name, "GRAY"))
                have.add(name)

        literals = ", ".join(
            f'{{name: {json.dumps(n)}, color: {c}, description: ""}}' for n, c in final
        )
        result = "projectV2Field{... on ProjectV2FieldCommon{id name}}"
        query = (
            "mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,"
            f"singleSelectOptions:[{literals}]}}){{{result}}}}}"
        )
        out = self._run(["gh", "api", "graphql", "-f", f"query={query}", "-f", f"f={field_id}"], None)
        node = json.loads(out)["data"]["updateProjectV2Field"]["projectV2Field"]
        return Field(id=node["id"], name=node["name"], data_type="SINGLE_SELECT",
                     options=[n for n, _ in final])

    def create_label(self, repo: str, name: str, color: str, description: str) -> None:
        self._run(
            [
                "gh", "label", "create", name, "--repo", repo,
                "--color", color, "--description", description, "--force",
            ],
            None,
        )
