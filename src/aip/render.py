"""Plain-text rendering of audit tables, plans, and health reports for the terminal."""

from __future__ import annotations

from aip.engine import HealthReport, SetupReport


def _row(label: str, value: str, width: int = 28) -> str:
    return f"{label:<{width}}{value}"


def render_audit(report: SetupReport) -> str:
    lines = ["AUDIT", ""]
    for f in report.file_findings + report.github_findings:
        detail = f" ({f.detail})" if f.detail else ""
        lines.append(_row(f.label, f"{f.status}{detail}"))
    return "\n".join(lines)


def render_plan(report: SetupReport) -> str:
    if report.total_actions == 0:
        return "Already compliant.\nNo changes required."
    lines = ["Proposed changes:", ""]
    for a in report.file_actions:
        flag = "  [needs confirmation]" if a.needs_confirmation else ""
        lines.append(f"  - {a.kind.value}: {a.path} ({a.reason}){flag}")
    for a in report.github_actions:
        lines.append(f"  - {a.kind.value}: {a.target} ({a.reason})")
    return "\n".join(lines)


def render_setup_result(report: SetupReport) -> str:
    if report.already_compliant:
        return "Already compliant.\nNo changes required."
    verb = "Would apply" if report.dry_run else "Applied"
    return f"{verb} {report.total_actions} change(s)."


def render_health(report: HealthReport) -> str:
    lines = ["AI PROJECT HEALTH", ""]
    for c in report.checks:
        verdict = "PASS" if c.status.name == "PRESENT" else ("WARN" if c.status.name == "PARTIAL" else "FAIL")
        detail = f"  ({c.detail})" if c.detail else ""
        lines.append(_row(c.label, verdict) + detail)

    snap = report.snapshot
    lines += [""]
    lines.append(_row("Current slice", str(snap.get("build_slice") or "—")))
    lines.append(_row("Current actor", str(snap.get("current_actor") or "—")))
    lines.append(_row("Next actor", str(snap.get("next_actor") or "—")))
    lines.append(_row("Review status", str(snap.get("review_status") or "—")))
    lines.append(_row("Human decisions", f"{report.open_human_decisions} open"))
    lines += ["", _row("Overall", "COMPLIANT" if report.compliant else "NON-COMPLIANT")]
    return "\n".join(lines)
