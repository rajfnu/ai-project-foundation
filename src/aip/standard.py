"""Definition of the AIP standard: the versioned set of things every adopted repo must have.

This module is pure data + light helpers. It does not touch the filesystem or GitHub.
The standard is versioned via ``STANDARD_VERSION`` so future ``aip upgrade`` work has an anchor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Bump when the standard's required shape changes in a way that adopted repos should migrate to.
STANDARD_VERSION = 1


@dataclass(frozen=True)
class RequiredPath:
    """A file or directory the standard expects to exist in an adopted repo.

    key:      stable identifier (dirs end with ``/``); also the human label in reports.
    path:     repo-relative path.
    is_dir:   True for directories, False for files.
    template: name of the template used to seed the file when missing (files only).
    managed:  True if aip owns a fenced block inside an existing file rather than
              overwriting it (e.g. AGENTS.md / CLAUDE.md).
    """

    key: str
    path: str
    is_dir: bool = False
    template: Optional[str] = None
    managed: bool = False


REQUIRED_PATHS: list[RequiredPath] = [
    RequiredPath("AGENTS.md", "AGENTS.md", template="AGENTS.md", managed=True),
    RequiredPath("CLAUDE.md", "CLAUDE.md", template="CLAUDE.md", managed=True),
    RequiredPath(".context/README.md", ".context/README.md", template="context_readme"),
    RequiredPath(".context/product/", ".context/product", is_dir=True),
    RequiredPath(".context/architecture/", ".context/architecture", is_dir=True),
    RequiredPath(".context/decisions/", ".context/decisions", is_dir=True),
    RequiredPath("docs/status/current.md", "docs/status/current.md", template="status_current_md"),
    RequiredPath("docs/status/current.yml", "docs/status/current.yml", template="status_current_yml"),
    RequiredPath("docs/handoffs/", "docs/handoffs", is_dir=True),
    RequiredPath("docs/process/github-sync.md", "docs/process/github-sync.md", template="process_sync"),
    RequiredPath("docs/process/github-project-views.md", "docs/process/github-project-views.md", template="process_views"),
    RequiredPath("evidence/", "evidence", is_dir=True),
    RequiredPath(".aip/config.yml", ".aip/config.yml", template="config"),
    RequiredPath(".aip/state.json", ".aip/state.json", template="state"),
]


# --- GitHub Project shape -------------------------------------------------------------

# Canonical Status stages (single-select). The 6-stage "Delivery Board" is a grouped VIEW
# over this field, not a second source of truth.
STATUS_STAGES: list[str] = [
    "Backlog",
    "Product Ready",
    "Architecture Ready",
    "Implementing",
    "Review",
    "Fix",
    "Accepted",
    "Customer Testing",
    "Done",
]

ACTOR_VALUES: list[str] = ["Human", "Architect", "Developer", "Reviewer", "Customer"]

REVIEW_STATUS_VALUES: list[str] = ["ACK", "GO", "CHECK", "FIX", "TECHNICALLY ACCEPTED"]

PRIORITY_VALUES: list[str] = ["P0", "P1", "P2", "P3"]

CUSTOMER_READY_VALUES: list[str] = ["No", "Ready", "In Testing", "Signed Off"]


@dataclass(frozen=True)
class ProjectField:
    """A GitHub Project (v2) custom field the standard requires."""

    name: str
    data_type: str  # "SINGLE_SELECT" | "TEXT"
    options: list[str] = field(default_factory=list)


REQUIRED_FIELDS: list[ProjectField] = [
    ProjectField("Status", "SINGLE_SELECT", STATUS_STAGES),
    ProjectField("Build / Slice", "TEXT"),
    ProjectField("Current Actor", "SINGLE_SELECT", ACTOR_VALUES),
    ProjectField("Next Actor", "SINGLE_SELECT", ACTOR_VALUES),
    ProjectField("Review Status", "SINGLE_SELECT", REVIEW_STATUS_VALUES),
    ProjectField("Priority", "SINGLE_SELECT", PRIORITY_VALUES),
    ProjectField("Customer Ready", "SINGLE_SELECT", CUSTOMER_READY_VALUES),
]


def project_title(repo: str) -> str:
    """Idempotency key for the owner-level Project, derived from the repo name."""
    return f"AIP · {repo}"


@dataclass(frozen=True)
class RequiredLabel:
    name: str
    color: str  # 6-hex, no '#'
    description: str


# Additive workflow labels. Brownfield never rewrites existing labels; it only adds
# missing ones from this set.
REQUIRED_LABELS: list[RequiredLabel] = [
    RequiredLabel("aip:blocked", "b60205", "Work is blocked"),
    RequiredLabel("aip:human-decision", "d93f0b", "Needs a human decision"),
    RequiredLabel("aip:under-review", "fbca04", "Under independent review"),
    RequiredLabel("aip:technically-accepted", "0e8a16", "Passed independent technical review"),
]
