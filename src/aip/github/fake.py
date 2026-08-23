"""In-memory GitHub client for offline, deterministic acceptance tests.

Mirrors the semantics aip relies on from real GitHub: owner-level Projects, single-select
fields with options, and repo labels. IDs are deterministic (no randomness) so tests can
assert on them and resume-style reruns are stable.
"""

from __future__ import annotations

from typing import Optional

from aip.github.client import Field, Project


class FakeGitHub:
    def __init__(self, owner: str, repo: str, labels: Optional[list[str]] = None):
        self.owner = owner
        self.repo = repo
        self._projects: dict[str, list[Project]] = {}
        self._fields: dict[str, list[Field]] = {}
        self._labels: dict[str, list[str]] = {f"{owner}/{repo}": list(labels or [])}
        self._seq = 0

    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq}"

    # --- read ---
    def find_project(self, owner: str, title: str) -> Optional[Project]:
        for project in self._projects.get(owner, []):
            if project.title == title:
                return project
        return None

    def list_fields(self, project_id: str) -> list[Field]:
        return list(self._fields.get(project_id, []))

    def list_labels(self, repo: str) -> list[str]:
        return list(self._labels.get(repo, []))

    # --- write ---
    def create_project(self, owner: str, title: str) -> Project:
        projects = self._projects.setdefault(owner, [])
        number = len(projects) + 1
        project = Project(id=self._next("PVT"), number=number, title=title)
        projects.append(project)
        # Mirror GitHub: every new Project v2 ships with a built-in single-select "Status"
        # field pre-populated with these defaults. aip must reconcile it, not recreate it.
        self._fields[project.id] = [
            Field(id=self._next("FLD"), name="Status", data_type="SINGLE_SELECT",
                  options=["Todo", "In Progress", "Done"])
        ]
        return project

    def create_field(
        self, project_id: str, name: str, data_type: str, options: list[str]
    ) -> Field:
        # Mirror GitHub: field names are unique per project.
        if any(f.name == name for f in self._fields.get(project_id, [])):
            raise ValueError("Name has already been taken")
        field = Field(id=self._next("FLD"), name=name, data_type=data_type, options=list(options))
        self._fields.setdefault(project_id, []).append(field)
        return field

    _GH_DEFAULT_STATUS = {"Todo", "In Progress", "Done"}

    def add_field_options(self, project_id: str, field_id: str, options: list[str]) -> Field:
        """Mirror GitHub semantics: replace the default Status set on a fresh field,
        otherwise union so nothing existing is destroyed. ``options`` is the full desired set."""
        fields = self._fields[project_id]
        for i, f in enumerate(fields):
            if f.id == field_id:
                base = [] if set(f.options) == self._GH_DEFAULT_STATUS else list(f.options)
                final = base + [o for o in options if o not in base]
                fields[i] = Field(f.id, f.name, f.data_type, final)
                return fields[i]
        raise KeyError(field_id)

    def create_label(self, repo: str, name: str, color: str, description: str) -> None:
        labels = self._labels.setdefault(repo, [])
        if name not in labels:
            labels.append(name)

    # --- test helpers ---
    def projects_for(self, owner: str) -> list[Project]:
        return list(self._projects.get(owner, []))

    def set_field_options(self, project_id: str, name: str, options: list[str]) -> None:
        """Test-only: set a field's options directly (e.g. seed a partial/complete Status)."""
        fields = self._fields[project_id]
        for i, f in enumerate(fields):
            if f.name == name:
                fields[i] = Field(f.id, f.name, f.data_type, list(options))
                return
        raise KeyError(name)
