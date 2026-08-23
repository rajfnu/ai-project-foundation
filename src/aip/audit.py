"""Audit engine: probe the current state of a repo against the standard.

Auditing NEVER mutates. It produces findings that later feed the planner.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path

from aip.standard import REQUIRED_PATHS


class Status(enum.Enum):
    PRESENT = "Present"
    PARTIAL = "Partial"
    MISSING = "Missing"

    def __str__(self) -> str:  # nicer report rendering
        return self.value


@dataclass(frozen=True)
class Finding:
    key: str
    label: str
    status: Status
    detail: str = ""


def audit_files(root: Path) -> list[Finding]:
    """Return one finding per required path, reflecting whether it exists in ``root``."""
    findings: list[Finding] = []
    for req in REQUIRED_PATHS:
        target = root / req.path
        if req.is_dir:
            present = target.is_dir()
        else:
            present = target.is_file()
        status = Status.PRESENT if present else Status.MISSING
        findings.append(Finding(key=req.key, label=req.key, status=status))
    return findings
