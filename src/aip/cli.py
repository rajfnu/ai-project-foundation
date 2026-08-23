"""`aip` command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from aip import __version__, render
from aip.engine import run_health, run_setup
from aip.github.gh import GhGitHub
from aip.preflight import PreflightError, ensure_gh, resolve_repo
from aip.standard import STANDARD_VERSION

app = typer.Typer(
    add_completion=False,
    help="AI Project Foundation — stamp a disciplined, visual AI-development operating model onto any GitHub repo.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the aip CLI version and the AIP standard version it implements."""
    typer.echo(f"aip {__version__} (standard {STANDARD_VERSION})")


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
