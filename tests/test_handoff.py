"""`aip handoff`: persist a protocol transition (ACK/GO/CHECK/FIX/TECHNICALLY ACCEPTED).

Writes a durable handoff record under docs/handoffs/ and updates docs/status/current.yml
so the repository — not chat — is the record of the transition. Mechanically enforces the
core invariant: a slice cannot be TECHNICALLY ACCEPTED by its own implementer.
"""

from pathlib import Path

import pytest
import yaml

from aip.engine import InvariantError, run_handoff, run_setup


def _repo(tmp_path: Path) -> Path:
    run_setup(tmp_path, None, "", "", dry_run=False, github_enabled=False)
    return tmp_path


def _status(tmp_path: Path) -> dict:
    return yaml.safe_load((tmp_path / "docs/status/current.yml").read_text())


TS = "2026-08-23T101010Z"


def test_go_creates_record_and_sets_status(tmp_path: Path):
    root = _repo(tmp_path)

    report = run_handoff(root, "GO", slice="Build 005A", note="build the thing", timestamp=TS)

    record = Path(report.record_path)
    assert record.exists()
    body = record.read_text()
    assert "GO" in body and "Build 005A" in body and "build the thing" in body

    status = _status(root)
    assert status["review_status"] == "GO"
    assert status["implementer"] == "Developer"
    assert status["build_slice"] == "Build 005A"


def test_check_then_fix_transitions(tmp_path: Path):
    root = _repo(tmp_path)
    run_handoff(root, "GO", slice="B1", timestamp=TS)

    run_handoff(root, "CHECK", timestamp="2026-08-23T101111Z")
    assert _status(root)["review_status"] == "CHECK"

    run_handoff(root, "FIX", note="rename foo", timestamp="2026-08-23T101212Z")
    assert _status(root)["review_status"] == "FIX"
    assert _status(root)["next_actor"] == "Developer"


def test_accepted_by_implementer_is_refused(tmp_path: Path):
    root = _repo(tmp_path)
    run_handoff(root, "GO", slice="B1", timestamp=TS)  # implementer = Developer

    with pytest.raises(InvariantError):
        run_handoff(root, "TECHNICALLY ACCEPTED", by="Developer", timestamp=TS)

    # status not advanced to accepted
    assert _status(root)["review_status"] != "TECHNICALLY ACCEPTED"


def test_accepted_by_independent_reviewer_succeeds(tmp_path: Path):
    root = _repo(tmp_path)
    run_handoff(root, "GO", slice="B1", timestamp=TS)

    report = run_handoff(root, "TECHNICALLY ACCEPTED", by="Reviewer", timestamp=TS)

    status = _status(root)
    assert status["review_status"] == "TECHNICALLY ACCEPTED"
    assert status["acceptor"] == "Reviewer"
    assert Path(report.record_path).exists()


def test_event_normalization_and_validation(tmp_path: Path):
    root = _repo(tmp_path)
    # alias forms accepted
    run_handoff(root, "accepted", by="Reviewer", timestamp=TS)
    assert _status(root)["review_status"] == "TECHNICALLY ACCEPTED"

    with pytest.raises(ValueError):
        run_handoff(root, "BOGUS", timestamp=TS)


def test_handoff_record_filename_is_timestamped_and_unique(tmp_path: Path):
    root = _repo(tmp_path)
    r1 = run_handoff(root, "ACK", timestamp="2026-08-23T101010Z")
    r2 = run_handoff(root, "GO", slice="B1", timestamp="2026-08-23T101011Z")
    assert r1.record_path != r2.record_path
    files = list((root / "docs/handoffs").glob("*.md"))
    assert len(files) == 2
