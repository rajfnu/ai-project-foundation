from pathlib import Path

from aip.audit import Status, audit_files
from aip.standard import REQUIRED_PATHS


def test_empty_repo_reports_all_paths_missing(tmp_path: Path):
    findings = audit_files(tmp_path)

    # one finding per required path in the standard
    assert {f.key for f in findings} == {r.key for r in REQUIRED_PATHS}
    assert findings, "standard must define at least one required path"
    assert all(f.status is Status.MISSING for f in findings)


def test_present_file_reported_present(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("hello")

    findings = {f.key: f for f in audit_files(tmp_path)}

    assert findings["AGENTS.md"].status is Status.PRESENT


def test_present_directory_reported_present(tmp_path: Path):
    (tmp_path / "evidence").mkdir()

    findings = {f.key: f for f in audit_files(tmp_path)}

    assert findings["evidence/"].status is Status.PRESENT
