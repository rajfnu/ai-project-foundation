"""Planner: turn the current repo state into an ordered list of concrete, idempotent actions.

Planning NEVER mutates. Each action is safe to describe in a dry-run and safe to skip if
already satisfied.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aip import managed
from aip import templates
from aip.standard import REQUIRED_PATHS, RequiredPath, STANDARD_VERSION


class ActionKind(enum.Enum):
    CREATE_DIR = "create directory"
    CREATE_FILE = "create file"
    UPDATE_MANAGED_BLOCK = "update managed block"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    key: str
    path: str
    reason: str
    needs_confirmation: bool = False


def _managed_block_for(req: RequiredPath) -> str:
    body = templates.managed_body(req.template)
    return managed.make_block(body, STANDARD_VERSION)


def _plan_one(root: Path, req: RequiredPath) -> Optional[Action]:
    target = root / req.path

    if req.is_dir:
        if target.is_dir():
            return None
        return Action(ActionKind.CREATE_DIR, req.key, req.path, reason="missing directory")

    # files
    if req.managed:
        block = _managed_block_for(req)
        if not target.exists():
            return Action(ActionKind.CREATE_FILE, req.key, req.path, reason="missing managed file")
        current = target.read_text()
        if managed.block_matches(current, block):
            return None
        reason = (
            "managed block missing — will append"
            if not managed.has_block(current)
            else "managed block out of date"
        )
        # touching an existing human-owned file: flag for confirmation
        return Action(
            ActionKind.UPDATE_MANAGED_BLOCK, req.key, req.path, reason=reason, needs_confirmation=True
        )

    # plain files: create if missing, never overwrite
    if target.is_file():
        return None
    return Action(ActionKind.CREATE_FILE, req.key, req.path, reason="missing file")


def plan_file_actions(root: Path) -> list[Action]:
    actions: list[Action] = []
    for req in REQUIRED_PATHS:
        action = _plan_one(root, req)
        if action is not None:
            actions.append(action)
    return actions
