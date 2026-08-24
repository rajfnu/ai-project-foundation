"""`aip` command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from aip import __version__, render
from aip.engine import (
    InvariantError,
    run_handoff,
    run_health,
    run_setup,
    run_sync,
    run_upgrade,
)
from aip.github.gh import GhGitHub
from aip.preflight import PreflightError, ensure_gh, resolve_repo
from aip.standard import STANDARD_VERSION
from aip.bootstrap import ProjectAnswers, write_project_brief

app = typer.Typer(
    add_completion=False,
    help="AI Project Foundation — stamp a disciplined, visual AI-development operating model onto any GitHub repo.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the aip CLI version and the AIP standard version it implements."""
    typer.echo(f"aip {__version__} (standard {STANDARD_VERSION})")


def _answer(value: str | None, prompt: str) -> str:
    return value.strip() if value and value.strip() else typer.prompt(prompt).strip()


@app.command("init")
def init_project(
    name: str = typer.Option(None, help="Project or product name."),
    objective: str = typer.Option(None, help="Problem and desired outcome."),
    users: str = typer.Option(None, help="Primary users and decision owners."),
    scope: str = typer.Option(None, help="Initial in-scope capability."),
    out_of_scope: str = typer.Option(None, "--out-of-scope", help="Explicit exclusions."),
    stack: str = typer.Option(None, help="Technology and existing assets."),
    deployment: str = typer.Option(None, help="Target runtime and environments."),
    data_classification: str = typer.Option(None, "--data", help="Data sensitivity and handling."),
    quality_gates: str = typer.Option(None, "--quality", help="Tests and acceptance expectations."),
    human_approvals: str = typer.Option(None, "--approvals", help="Actions reserved for humans."),
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Establish Standard v2 and conduct the ten-question project foundation interview."""
    root = path.resolve()
    run_setup(root, None, "", "", dry_run=False, github_enabled=False)
    answers = ProjectAnswers(
        name=_answer(name, "1/10 Project name"),
        objective=_answer(objective, "2/10 Problem and desired outcome"),
        users=_answer(users, "3/10 Primary users and decision owners"),
        scope=_answer(scope, "4/10 Initial scope"),
        out_of_scope=_answer(out_of_scope, "5/10 Explicitly out of scope"),
        stack=_answer(stack, "6/10 Technology and existing assets"),
        deployment=_answer(deployment, "7/10 Deployment target"),
        data_classification=_answer(data_classification, "8/10 Data classification"),
        quality_gates=_answer(quality_gates, "9/10 Quality and acceptance gates"),
        human_approvals=_answer(human_approvals, "10/10 Human approvals"),
    )
    try:
        brief = write_project_brief(root, answers)
    except FileExistsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    typer.echo(f"Initialized {answers.name}. Project brief: {brief.relative_to(root)}")
    typer.echo("Review the generated foundation, then run `aip setup` to connect GitHub.")


def _prepare(no_github: bool):
    """Resolve repo + client, or exit with a helpful message."""
    if no_github:
        return None, "", ""
    try:
        ensure_gh()
        owner, repo = resolve_repo()
    except PreflightError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    return GhGitHub(), owner, repo


@app.command()
def setup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change; modify nothing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without an interactive prompt."),
    no_github: bool = typer.Option(False, "--no-github", help="Only manage repository files."),
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Audit the repo against the AIP standard and add only what is missing (idempotent)."""
    client, owner, repo = _prepare(no_github)
    root = path.resolve()

    # Always audit + plan first (never mutates).
    report = run_setup(root, client, owner, repo, dry_run=True, github_enabled=not no_github)
    typer.echo(render.render_audit(report))
    typer.echo("")
    typer.echo(render.render_plan(report))

    if report.already_compliant:
        raise typer.Exit(code=0)
    if dry_run:
        typer.echo("\nDry run — nothing was changed.")
        raise typer.Exit(code=0)

    if not yes:
        typer.echo("")
        if not typer.confirm("Apply these changes?"):
            typer.echo("Aborted. Nothing was changed.")
            raise typer.Exit(code=1)

    applied = run_setup(root, client, owner, repo, dry_run=False, github_enabled=not no_github)
    typer.echo("")
    typer.echo(render.render_setup_result(applied))
    if applied.sync is not None:
        typer.echo(
            f"Synced slice '{applied.sync.item_title}' to the Project "
            f"({len(applied.sync.fields_set)} field(s))."
        )


@app.command()
def sync(
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Push docs/status/current.yml into the current slice's GitHub Project item (one-way)."""
    client, owner, repo = _prepare(no_github=False)
    root = path.resolve()
    try:
        report = run_sync(root, client, owner, repo)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    verb = "Created" if report.created else "Updated"
    typer.echo(
        f"{verb} Project item '{report.item_title}' — set {len(report.fields_set)} field(s): "
        f"{', '.join(report.fields_set) or '(none)'}"
    )


@app.command()
def upgrade(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change; modify nothing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without an interactive prompt."),
    no_github: bool = typer.Option(False, "--no-github", help="Only manage repository files."),
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Bring the repo up to the current AIP standard version (migrations + re-converge)."""
    client, owner, repo = _prepare(no_github)
    root = path.resolve()

    preview = run_upgrade(root, client, owner, repo, dry_run=True, github_enabled=not no_github)
    typer.echo(f"Standard version: {preview.from_version} -> {preview.to_version}")
    if preview.migrations_run:
        typer.echo(f"Migrations to run: {', '.join(map(str, preview.migrations_run))}")
    typer.echo("")
    typer.echo(render.render_plan(preview.setup))

    if not preview.changed:
        typer.echo(f"\nAlready at standard version {preview.to_version}. No changes required.")
        raise typer.Exit(code=0)
    if dry_run:
        typer.echo("\nDry run — nothing was changed.")
        raise typer.Exit(code=0)
    if not yes and not typer.confirm("\nApply this upgrade?"):
        typer.echo("Aborted. Nothing was changed.")
        raise typer.Exit(code=1)

    applied = run_upgrade(root, client, owner, repo, dry_run=False, github_enabled=not no_github)
    typer.echo(
        f"\nUpgraded to standard version {applied.to_version} "
        f"({len(applied.migrations_run)} migration(s), {applied.setup.total_actions} standard change(s))."
    )


@app.command()
def handoff(
    event: str = typer.Argument(..., help="ACK | GO | CHECK | FIX | TECHNICALLY-ACCEPTED"),
    by: str = typer.Option(None, "--by", help="Actor performing the transition (e.g. Reviewer)."),
    slice_: str = typer.Option(None, "--slice", help="Build / slice this handoff concerns."),
    note: str = typer.Option(None, "--note", help="Free-text note for the record."),
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Record a protocol transition: write a handoff record and update current status."""
    root = path.resolve()
    try:
        report = run_handoff(root, event, by=by, slice=slice_, note=note)
    except (ValueError, InvariantError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    rel = Path(report.record_path)
    try:
        rel = rel.relative_to(root)
    except ValueError:
        pass
    typer.echo(f"Recorded {report.event}. Review status -> {report.review_status}.")
    typer.echo(f"Handoff: {rel}")
    typer.echo("Run `aip sync` to reflect this on the GitHub Project board.")


@app.command()
def health(
    no_github: bool = typer.Option(False, "--no-github", help="Only check repository files."),
    path: Path = typer.Option(Path("."), "--path", help="Repository root.", show_default=False),
) -> None:
    """Inspect the repo + GitHub Project and report compliance. Exits non-zero if not compliant."""
    client, owner, repo = _prepare(no_github)
    root = path.resolve()
    report = run_health(root, client, owner, repo, github_enabled=not no_github)
    typer.echo(render.render_health(report))
    raise typer.Exit(code=0 if report.compliant else 1)


if __name__ == "__main__":
    app()
