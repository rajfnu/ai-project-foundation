"""`aip upgrade`: bring an adopted repo up to the current AIP standard version.

The standard is versioned; each repo records its standard_version in .aip/config.yml.
upgrade runs any registered migrations between the repo's version and the current one,
re-converges the standard (adds newly-required files/fields/views, refreshes managed
blocks), and stamps the new version. Idempotent when already current.
"""

from pathlib import Path

from aip.config import read_config
from aip.engine import migrations_to_run, run_setup, run_upgrade
from aip.github.fake import FakeGitHub
from aip.standard import STANDARD_VERSION


def test_migrations_to_run_selects_intermediate_versions_in_order():
    registry = {1: "a", 2: "b", 3: "c"}
    assert migrations_to_run(1, 3, registry) == [2, 3]
    assert migrations_to_run(0, 2, registry) == [1, 2]
    assert migrations_to_run(3, 3, registry) == []
    assert migrations_to_run(5, 3, registry) == []


def _downgrade_config(tmp_path: Path, version: int):
    p = tmp_path / ".aip/config.yml"
    text = p.read_text()
    import re
    p.write_text(re.sub(r"(?m)^standard_version:.*$", f"standard_version: {version}", text))


def test_upgrade_bumps_config_version(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    _downgrade_config(tmp_path, 0)  # pretend this repo adopted an older standard

    report = run_upgrade(tmp_path, client, "acme", "widget", dry_run=False)

    assert report.from_version == 0
    assert report.to_version == STANDARD_VERSION
    assert report.changed is True
    assert read_config(tmp_path).standard_version == STANDARD_VERSION


def test_upgrade_already_latest_is_noop(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    report = run_upgrade(tmp_path, client, "acme", "widget", dry_run=False)

    assert report.from_version == STANDARD_VERSION
    assert report.to_version == STANDARD_VERSION
    assert report.changed is False


def test_upgrade_dry_run_changes_nothing(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    _downgrade_config(tmp_path, 0)

    report = run_upgrade(tmp_path, client, "acme", "widget", dry_run=True)

    assert report.applied is False
    assert read_config(tmp_path).standard_version == 0  # unchanged on disk


def test_upgrade_refreshes_stale_managed_block(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    agents = tmp_path / "AGENTS.md"
    # simulate an old managed block body while keeping the human content + markers
    import re
    stale = re.sub(
        r"(?s)(<!-- AIP:BEGIN[^\n]*-->\n).*(\n<!-- AIP:END -->)",
        r"\1OUTDATED CONTENT\2",
        agents.read_text(),
    )
    agents.write_text(stale)

    run_upgrade(tmp_path, client, "acme", "widget", dry_run=False)

    assert "OUTDATED CONTENT" not in agents.read_text()
    assert "AIP Operating Model" in agents.read_text()
