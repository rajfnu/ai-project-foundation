# AI Project Foundation (`aip`)

`aip` stamps a disciplined, visual AI-development operating model onto any GitHub
repository — greenfield or brownfield — so every project runs the same way without
recreating the setup by hand.

It is completely project-agnostic. It references patterns proven on other projects but
copies no customer data, secrets, prompts, or application code.

## What it establishes

- **Two-role delivery discipline** — Architect/Reviewer ⇄ Developer, with a hard
  invariant: *the agent that implements a slice cannot technically accept its own work.*
  Which model/provider fills each role is configuration, not code.
- **Repository as memory** — product, architecture, decisions, current slice, actors,
  work orders, CHECK/FIX/acceptance, and evidence live in files, not chat.
- **A GitHub Project cockpit** — a workflow board and custom fields that mirror (not
  duplicate) repository state.
- **A lightweight protocol** — ACK / GO / CHECK / FIX / TECHNICALLY ACCEPTED.

## Commands

```bash
aip setup   [--dry-run] [--yes] [--no-github] [--path DIR]
aip sync    [--path DIR]
aip handoff <ACK|GO|CHECK|FIX|TECHNICALLY-ACCEPTED> [--by ACTOR] [--slice S] [--note N]
aip upgrade [--dry-run] [--yes] [--no-github] [--path DIR]
aip health  [--no-github] [--path DIR]
aip version
```

- `aip setup` audits the repo against the AIP standard and adds **only what is missing**.
  It is idempotent (a second run reports `Already compliant`) and never overwrites human
  content — `AGENTS.md`/`CLAUDE.md` are edited only inside a fenced `AIP:BEGIN…AIP:END`
  block. `--dry-run` shows the exact plan and mutates nothing.
- `aip sync` reads `docs/status/current.yml` and pushes the current slice onto the GitHub
  Project as a single item (Status, Build / Slice, Current/Next Actor, Review Status,
  Priority, Customer Ready). One-way and idempotent — the repository is the source of
  truth, the board is its projection. `aip setup` runs it automatically once a real slice
  exists (a fresh greenfield setup leaves no placeholder card).
- `aip handoff <EVENT>` persists a protocol transition: it writes a durable record under
  `docs/handoffs/`, updates `docs/status/current.yml` (review status, actors, implementer/
  acceptor), and **refuses `TECHNICALLY ACCEPTED` from the slice's own implementer** — the
  independent-review invariant enforced at the moment of transition, not just in `health`.
- `aip upgrade` brings an adopted repo to the current AIP standard version: runs any
  registered migrations between the repo's `standard_version` and the current one,
  re-converges the standard (new files/fields/views, refreshed managed blocks), and stamps
  the new version. Idempotent when already current.
- `aip health` reports PASS/FAIL against each requirement plus the current slice snapshot,
  and enforces the independent-review invariant. Exit code is non-zero when not compliant.

## GitHub automation & honest limits

`aip` fully automates creating the Project and **all custom fields/options** via `gh` and
the GitHub GraphQL API. The Projects (v2) API does not expose reliable creation of *view
layouts*; those four views are a documented one-time manual step (see
`docs/process/github-project-views.md`, generated at setup). Everything else is automated
and verified by `aip health`.

The repository (`docs/status/current.yml`) is the source of truth; the Project is its
visual projection (`docs/process/github-sync.md`).

## Configuration

`.aip/config.yml` binds agents to roles and toggles workflow switches. Swapping which
agent is Architect vs. Developer is a config edit — never a rewrite.

```yaml
standard_version: 1
roles:
  architect_reviewer: { agent: opus }   # example — any model/provider
  developer:          { agent: codex }
github:   { project: true }
workflow: { independent_review_required: true }
```

## Development

```bash
uv sync
uv run pytest        # 38 tests, offline (GitHub behind a fake client)
uv run aip --help
```

The standard is versioned (`standard_version`) so a future `aip upgrade` has an anchor.
