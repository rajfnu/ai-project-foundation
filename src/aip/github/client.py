"""GitHub client abstraction.

The engine depends only on this Protocol. Two implementations exist:
- FakeGitHub (in-memory, for fast offline acceptance tests)
- GhGitHub (shells out to `gh` / `gh api graphql`)

All methods must be safe to call as part of an idempotent converge: readers never mutate,
and creators are only invoked by the applier after the planner has confirmed the thing is
missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass(frozen=True)
class Project:
    id: str
    number: int
    title: str


@dataclass(frozen=True)
class Field:
    id: str
    name: str
    data_type: str  # "SINGLE_SELECT" | "TEXT"
    options: list[str] = field(default_factory=list)  # option names, for SINGLE_SELECT


@dataclass
class Item:
    id: str
    title: str
    values: dict = field(default_factory=dict)  # field name -> value (as displayed)


class GitHubClient(Protocol):
    # --- read ---
    def find_project(self, owner: str, title: str) -> Optional[Project]: ...
    def list_fields(self, project_id: str) -> list[Field]: ...
    def list_labels(self, repo: str) -> list[str]: ...
    def list_items(self, project_id: str) -> list[Item]: ...

    # --- write (only called by the applier / sync) ---
    def create_project(self, owner: str, title: str) -> Project: ...
    def create_field(
        self, project_id: str, name: str, data_type: str, options: list[str]
    ) -> Field: ...
    def add_field_options(self, project_id: str, field_id: str, options: list[str]) -> Field: ...
    def create_label(self, repo: str, name: str, color: str, description: str) -> None: ...
    def add_draft_item(self, project_id: str, title: str) -> Item: ...
    def set_field_value(
        self, project_id: str, item_id: str, field: Field, value: str
    ) -> None: ...
