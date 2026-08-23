"""In-memory GitHub client for offline, deterministic acceptance tests.

Mirrors the semantics aip relies on from real GitHub: owner-level Projects, single-select
fields with options, and repo labels. IDs are deterministic (no randomness) so tests can
assert on them and resume-style reruns are stable.
"""

from __future__ import annotations

from typing import Optional

from aip.github.client import Field, Item, Project, View


class FakeGitHub:
    def __init__(self, owner: str, repo: str, labels: Optional[list[str]] = None):
        self.owner = owner
        self.repo = repo
        self._projects: dict[str, list[Project]] = {}
        self._fields: dict[str, list[Field]] = {}
        self._labels: dict[str, list[str]] = {f"{owner}/{repo}": list(labels or [])}
        self._items: dict[str, list[Item]] = {}
        self._views: dict[str, list[View]] = {}
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
        # Mirror GitHub: a new project ships with one default table view.
        self._views[project.id] = [
            View(id=self._next("VIEW"), name="View 1", layout="TABLE_LAYOUT")
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

    def list_items(self, project_id: str) -> list[Item]:
        return list(self._items.get(project_id, []))

    def add_draft_item(self, project_id: str, title: str) -> Item:
        item = Item(id=self._next("ITM"), title=title, values={})
        self._items.setdefault(project_id, []).append(item)
        return item

    def set_field_value(self, project_id: str, item_id: str, field: Field, value: str) -> None:
        for item in self._items.get(project_id, []):
            if item.id == item_id:
                item.values[field.name] = value
                return
        raise KeyError(item_id)

    def list_views(self, project_id: str) -> list[View]:
        return list(self._views.get(project_id, []))

    def create_view(self, project_id: str, name: str, layout: str) -> View:
        view = View(id=self._next("VIEW"), name=name, layout=layout)
        self._views.setdefault(project_id, []).append(view)
        return view

    def update_view(
        self, project_id: str, view_id: str, filter: str, visible_field_ids: list
    ) -> None:
        for view in self._views.get(project_id, []):
            if view.id == view_id:
                view.filter = filter
                view.visible_field_ids = list(visible_field_ids)
                return
        raise KeyError(view_id)

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
