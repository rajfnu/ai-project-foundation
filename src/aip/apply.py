"""Applier: execute planned actions against the filesystem.

Each action is idempotent and additive. Managed files are only ever touched inside the
aip block; plain files are never overwritten (the planner won't emit an action for them
if they already exist).
"""

from __future__ import annotations

from pathlib import Path

from aip import managed
from aip import templates
from aip.plan import Action, ActionKind
from aip.standard import REQUIRED_PATHS, STANDARD_VERSION

_BY_KEY = {r.key: r for r in REQUIRED_PATHS}


def _create_dir(root: Path, action: Action) -> None:
    target = root / action.path
    target.mkdir(parents=True, exist_ok=True)
    # keep otherwise-empty dirs trackable by git
    gitkeep = target / ".gitkeep"
    if not any(target.iterdir()):
        gitkeep.write_text("")


def _create_file(root: Path, action: Action) -> None:
    req = _BY_KEY[action.key]
    target = root / action.path
    target.parent.mkdir(parents=True, exist_ok=True)
    if req.managed:
        body = templates.managed_body(req.template)
        block = managed.make_block(body, STANDARD_VERSION)
        content = f"{templates.managed_title(req.template)}\n\n{block}\n"
    else:
        content = templates.render_plain(req.template)
    target.write_text(content)


def _update_managed_block(root: Path, action: Action) -> None:
    req = _BY_KEY[action.key]
    target = root / action.path
    body = templates.managed_body(req.template)
    block = managed.make_block(body, STANDARD_VERSION)
    current = target.read_text() if target.exists() else ""
    target.write_text(managed.upsert_block(current, block))


_HANDLERS = {
    ActionKind.CREATE_DIR: _create_dir,
    ActionKind.CREATE_FILE: _create_file,
    ActionKind.UPDATE_MANAGED_BLOCK: _update_managed_block,
}


def apply_actions(root: Path, actions: list[Action]) -> None:
    for action in actions:
        _HANDLERS[action.kind](root, action)
