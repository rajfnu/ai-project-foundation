"""Safety: aip must not read, store, or emit credentials."""

import json
from pathlib import Path

from aip.engine import run_setup
from aip.github.fake import FakeGitHub

SECRETY = ("token", "secret", "password", "ghp_", "authorization", "apikey", "api_key")


def test_state_json_contains_no_secrets(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    state = json.loads((tmp_path / ".aip/state.json").read_text())
    assert set(state.keys()) <= {"standard_version", "github"}
    blob = json.dumps(state).lower()
    assert not any(word in blob for word in SECRETY)


def test_generated_files_contain_no_secrets(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    for p in tmp_path.rglob("*"):
        if p.is_file():
            text = p.read_text().lower()
            assert "ghp_" not in text and "authorization:" not in text
