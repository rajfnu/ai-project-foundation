"""Preflight checks and repo resolution via the `gh` CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional


class PreflightError(RuntimeError):
    """Raised with a human-actionable remediation message."""


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PreflightError(proc.stderr.strip() or f"command failed: {' '.join(args)}")
    return proc.stdout


def ensure_gh() -> None:
    if shutil.which("gh") is None:
        raise PreflightError(
            "GitHub CLI (`gh`) not found. Install it from https://cli.github.com/ and run `gh auth login`."
        )
    proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise PreflightError("Not authenticated with GitHub. Run `gh auth login`.")


def resolve_repo() -> tuple[str, str]:
    """Return (owner, name) for the current repo, or raise PreflightError."""
    try:
        out = _run(["gh", "repo", "view", "--json", "owner,name"])
    except PreflightError as exc:
        raise PreflightError(
            "Could not determine the GitHub repository. Run inside a repo with a GitHub remote.\n"
            f"  detail: {exc}"
        ) from exc
    data = json.loads(out)
    return data["owner"]["login"], data["name"]
