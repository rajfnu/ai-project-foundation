# AI Project Foundation (`aip`)

`aip` stamps a disciplined, visual AI-development operating model onto any GitHub
repository — greenfield or brownfield — so every project runs the same way without
recreating the setup by hand.

It is completely project-agnostic. It references patterns proven on other projects but
copies no customer data, secrets, prompts, or application code.

## What it establishes

- **A complete project foundation** — guided product brief plus Core, Requirements,
  Acceptance, Architecture, Plan, Constraints, Guardrails, Decisions and Runbook templates.
- **Role-separated delivery discipline** — Lead Orchestrator, Product Owner, Architect,
  Developer and Independent Reviewer, with a hard
  invariant: *the agent that implements a slice cannot technically accept its own work.*
  Which model/provider fills each role is configuration, not code.
- **Repository as memory** — product, architecture, decisions, current slice, actors,
  work orders, CHECK/FIX/acceptance, and evidence live in files, not chat.
- **A GitHub Project cockpit** — a workflow board and custom fields that mirror (not
  duplicate) repository state.
- **A lightweight protocol** — ACK / GO / CHECK / FIX / TECHNICALLY ACCEPTED.

## Getting started

### Prerequisites
- **Python 3.9+**
- **[GitHub CLI](https://cli.github.com/) (`gh`)**, authenticated with the `project` scope:
  ```bash
  gh auth login
  gh auth refresh -s project        # grant Projects v2 access (needed to create the board)
  ```
  (You can skip `gh` entirely and manage only the repository files with `--no-github`.)

### Install
Not yet published to PyPI — install from a clone:
```bash
git clone https://github.com/rajfnu/ai-project-foundation.git
cd ai-project-foundation
uv tool install .          # puts `aip` on your PATH  (or: pipx install .)
aip version
```
For local development instead, use an editable install: `uv sync && uv pip install -e .`.

### Quickstart
```bash
cd your-repo                # a new/empty repo OR an existing project

aip init                   # ten-question guided project foundation interview
aip setup --dry-run        # audit + see exactly what would change (mutates nothing)
aip setup                  # review the plan, confirm, and apply only what's missing
aip health                 # confirm COMPLIANT

# day-to-day: record transitions in the repo, then reflect them on the board
aip handoff GO --slice "Build 001A" --note "implement search"
aip handoff CHECK
aip handoff TECHNICALLY-ACCEPTED --by Reviewer
aip sync                   # push current status to the GitHub Project
```
Running against an existing project (brownfield) is safe: `aip setup` audits first, adds
only what's missing, and never overwrites your code, history, issues, PRs, or the human
parts of `AGENTS.md`/`CLAUDE.md`. Use `--dry-run` first to preview.

## Commands

```bash
aip init    [--path DIR] [ten optional non-interactive answer flags]
aip setup   [--dry-run] [--yes] [--no-github] [--path DIR]
aip sync    [--path DIR]
aip handoff <ACK|GO|CHECK|FIX|TECHNICALLY-ACCEPTED> [--by ACTOR] [--slice S] [--note N]
aip upgrade [--dry-run] [--yes] [--no-github] [--path DIR]
aip health  [--no-github] [--path DIR]
aip version
```

- `aip init` establishes the Standard v2 files and conducts a ten-question interview covering
  objective, users, scope, exclusions, stack, deployment, data, quality and human authority.
  It writes `.context/product/PROJECT_BRIEF.md` and refuses to overwrite an initialized brief.
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

`aip` fully automates creating the Project, **all custom fields/options**, and the four
**views** (Delivery Board, Current Work, Decisions / Blockers, Accepted / History) via `gh`
and the GitHub GraphQL API — layout, filter, and visible columns included. The one honest
limitation is *custom grouping* for a Table view, which the Projects (v2) API doesn't expose
(a Board layout auto-groups by Status); it's documented in `docs/process/github-project-views.md`,
generated at setup. Everything else is automated and verified by `aip health`.

The repository (`docs/status/current.yml`) is the source of truth; the Project is its
visual projection (`docs/process/github-sync.md`).

## Configuration

`.aip/config.yml` binds agents to roles and declares provider references, tools, notification
adapters and workflow switches. It contains no credentials: `secret_ref` points to an environment
variable, keychain or vault. Swapping a model or provider is configuration — never a rewrite.

```yaml
standard_version: 2
roles:
  lead_orchestrator:    { provider: anthropic, model: configurable }
  product_owner:        { provider: anthropic, model: configurable }
  architect:            { provider: anthropic, model: configurable }
  developer:            { agent: codex, provider: openai, model: configurable }
  independent_reviewer: { provider: anthropic, model: configurable }
providers:
  anthropic: { secret_ref: env:ANTHROPIC_API_KEY }
  openai:    { secret_ref: env:OPENAI_API_KEY }
github:   { project: true }
workflow: { independent_review_required: true }
```

Standard v2 remains an operating-model and control-plane foundation. Provider execution,
long-running agent supervision and notification delivery are the next runtime layer; the v2
configuration gives those adapters a stable, non-secret contract.

## Development

```bash
uv sync
uv run pytest        # 78 tests, offline (GitHub behind a fake client)
uv run aip --help
```

The standard is versioned (`standard_version`); `aip upgrade` migrates an adopted repo to
the current version.
