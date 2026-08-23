"""Template content for the standard's files.

Kept as module constants/functions (no external template files) so the package is
dependency-light and the exact rendered output is easy to assert in tests.
"""

from __future__ import annotations

import json

from aip.standard import STANDARD_VERSION

# --- managed-block bodies (owned by aip inside otherwise human files) -----------------

AGENTS_MANAGED_BODY = """\
## AIP Operating Model (managed by `aip` — do not hand-edit inside this block)

This repository follows the **AI Project Foundation** operating model. This block is the
shared authoritative instruction for every coding agent working here.

### Roles (not models)
Two interchangeable engineering roles. Which model/provider fills each role is set in
`.aip/config.yml` — roles are swappable without changing this operating model.

- **Architect / Reviewer** — plans slices, performs independent review, accepts or rejects.
- **Developer** — implements the authorized slice.

**Invariant:** the agent that implements a slice MUST NOT technically accept its own
implementation. Acceptance is only valid from a different actor than the implementer.

### Delivery protocol
- **ACK** — actor has read and understood the current work.
- **GO** — bounded work is authorized.
- **CHECK** — implementer believes the work is ready for independent review.
- **FIX** — independent reviewer found required changes (returns to Developer).
- **TECHNICALLY ACCEPTED** — independent technical review passed.

### Repository is memory, chat is coordination
Material product decisions, architecture decisions, work orders, CHECK results, FIX
findings, acceptance results, evidence, and current handoff state MUST be persisted in
this repository — not left in chat. A fresh agent session must be able to reconstruct
project state from files alone:

- `/.context/product/` — what the product is.
- `/.context/architecture/` — current architecture.
- `/.context/decisions/` — important decisions.
- `/docs/status/current.md` (+ `current.yml`) — current slice, actor, next actor, review status.
- `/docs/handoffs/` — handoff records at transitions.
- `/evidence/` — evidence backing acceptance.

The GitHub Project is the human's visual projection of `/docs/status/`; the repository
is the source of truth. See `docs/process/` for the sync rule.
"""

CLAUDE_MANAGED_BODY = """\
## AIP

This project uses the **AI Project Foundation** operating model. The authoritative agent
instructions live in [`AGENTS.md`](./AGENTS.md). Read and follow `AGENTS.md`; do not
duplicate or contradict it here.
"""

# --- plain files ----------------------------------------------------------------------

CONTEXT_README = """\
# .context

Durable project memory for coding agents. See `AGENTS.md` for the operating model.

- `product/` — what the product is (problem, users, scope).
- `architecture/` — current architecture and key components.
- `decisions/` — important decisions (one file per decision).
"""

STATUS_CURRENT_MD = """\
# Current Status

> Source of truth for the current slice. The GitHub Project mirrors this file.

- **Build / Slice:** UNKNOWN — needs human confirmation
- **Current Actor:** UNKNOWN
- **Next Actor:** UNKNOWN
- **Review Status:** —

## Open human decisions
- (none recorded)
"""

STATUS_CURRENT_YML = """\
# Machine-readable mirror of docs/status/current.md (source of truth for `aip sync`).
# `aip sync` pushes these values into the GitHub Project item for the current slice.
status: null           # one of the 9 Status stages (Board column), e.g. Implementing
build_slice: null      # e.g. Build 005A
current_actor: null    # Human | Architect | Developer | Reviewer | Customer
next_actor: null
review_status: null    # ACK | GO | CHECK | FIX | TECHNICALLY ACCEPTED
priority: null         # P0 | P1 | P2 | P3
customer_ready: null   # No | Ready | In Testing | Signed Off
implementer: null      # actor who implemented the current slice (enforces the acceptance invariant)
acceptor: null         # actor who technically accepted it, if any
open_human_decisions: []
blocked: false
"""

PROCESS_SYNC = """\
# Repository <-> GitHub Project synchronization

**The repository is the source of truth.** `docs/status/current.yml` is authoritative for
slice, actors, review status, and open human decisions.

- `aip sync` pushes those values into the GitHub Project's fields.
- Humans may re-arrange cards in the Project for convenience, but on the next `aip sync`
  or `aip health` the repository wins and any drift is reported.
- The GitHub Project is a visual projection, never a second source of truth.
"""


PROCESS_VIEWS = """\
# GitHub Project views — one-time manual setup

`aip` creates the Project and **all custom fields/options** automatically. The GitHub
Projects (v2) API does not expose reliable creation of *view layouts* (board vs. table,
grouping, filters, visible columns), so those are the one honest manual step. Create these
four views once; everything else stays automated and is verified by `aip health`.

1. **Delivery Board** — layout: Board, group by `Status`.
   Columns follow the workflow: Backlog → Product Ready → Architecture Ready →
   Implementing → Review → Fix → Accepted → Customer Testing → Done.
2. **Current Work** — layout: Table, filter `Status` is not Done/Accepted.
   Show: Build / Slice, Current Actor, Next Actor, Review Status, Priority.
3. **Decisions / Blockers** — layout: Table, filter label `aip:human-decision` or
   `aip:blocked`.
4. **Accepted / History** — layout: Table, filter `Review Status` is `TECHNICALLY ACCEPTED`
   or `Status` is Accepted/Done.

The repository (`docs/status/current.yml`) remains the source of truth; the Project is its
visual projection. See `github-sync.md`.
"""


def config_yaml() -> str:
    return f"""\
# AI Project Foundation — project configuration.
# Roles are structural; the agent (model/provider) filling each role is configuration.
standard_version: {STANDARD_VERSION}

roles:
  architect_reviewer:
    agent: opus       # example — any model/provider; swap freely
  developer:
    agent: codex      # example — any model/provider; swap freely

github:
  project: true       # create/adopt a GitHub Project for visualization

workflow:
  independent_review_required: true   # a slice cannot be accepted by its own implementer

paths: {{}}            # brownfield: map standard paths onto existing equivalents
"""


def state_json(project: dict | None = None) -> str:
    state = {
        "standard_version": STANDARD_VERSION,
        "github": {"project": project},
    }
    return json.dumps(state, indent=2) + "\n"


# --- template registry ----------------------------------------------------------------

# Non-managed file templates keyed by RequiredPath.template.
PLAIN_TEMPLATES: dict[str, str] = {
    "context_readme": CONTEXT_README,
    "status_current_md": STATUS_CURRENT_MD,
    "status_current_yml": STATUS_CURRENT_YML,
    "process_sync": PROCESS_SYNC,
    "process_views": PROCESS_VIEWS,
}


def managed_body(template: str) -> str:
    """Return the managed-block body for a managed file template."""
    return {"AGENTS.md": AGENTS_MANAGED_BODY, "CLAUDE.md": CLAUDE_MANAGED_BODY}[template]


def managed_title(template: str) -> str:
    return {"AGENTS.md": "# AGENTS", "CLAUDE.md": "# CLAUDE"}[template]


def render_plain(template: str) -> str:
    """Render a non-managed file template by name."""
    if template == "config":
        return config_yaml()
    if template == "state":
        return state_json()
    return PLAIN_TEMPLATES[template]
