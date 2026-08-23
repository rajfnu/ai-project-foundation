"""Read .aip/config.yml — the role<->agent binding and workflow switches.

Roles are structural and fixed; the agent (model/provider) filling each role is pure
configuration. Swapping the two agents is a config edit, never a code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = ".aip/config.yml"


@dataclass(frozen=True)
class Config:
    standard_version: int
    architect_reviewer_agent: str | None
    developer_agent: str | None
    github_project: bool
    independent_review_required: bool
    raw: dict


def read_config(root: Path) -> Config:
    path = root / CONFIG_PATH
    data = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text())
        if isinstance(loaded, dict):
            data = loaded
    roles = data.get("roles") or {}
    return Config(
        standard_version=data.get("standard_version", 0),
        architect_reviewer_agent=(roles.get("architect_reviewer") or {}).get("agent"),
        developer_agent=(roles.get("developer") or {}).get("agent"),
        github_project=bool((data.get("github") or {}).get("project", True)),
        independent_review_required=bool(
            (data.get("workflow") or {}).get("independent_review_required", True)
        ),
        raw=data,
    )


def set_standard_version(root: Path, version: int) -> None:
    """Update standard_version in .aip/config.yml, preserving comments and layout."""
    path = root / CONFIG_PATH
    text = path.read_text() if path.is_file() else ""
    line = f"standard_version: {version}"
    if re.search(r"(?m)^standard_version:.*$", text):
        text = re.sub(r"(?m)^standard_version:.*$", line, text)
    else:
        text = line + "\n" + text
    path.write_text(text)
