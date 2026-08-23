"""Read/write .aip/state.json — the non-secret mapping aip needs across runs.

Holds the adopted Project's id/number so re-runs and `aip health` can find it without
re-searching, plus the standard version stamped at setup time. Never stores credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from aip.github.client import Project
from aip.standard import STANDARD_VERSION

STATE_PATH = ".aip/state.json"


def read_state(root: Path) -> dict:
    path = root / STATE_PATH
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def write_project(root: Path, project: Optional[Project]) -> None:
    path = root / STATE_PATH
    state = read_state(root) or {"standard_version": STANDARD_VERSION, "github": {"project": None}}
    state.setdefault("github", {})
    state["github"]["project"] = (
        None if project is None else {"id": project.id, "number": project.number, "title": project.title}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
