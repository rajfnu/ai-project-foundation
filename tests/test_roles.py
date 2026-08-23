"""Role swapping + the independent-review invariant.

The operating model is expressed over ROLES/ACTORS, so swapping which agent fills each
role changes configuration only — the invariant (an implementer cannot accept its own
slice) holds identically in both configurations.
"""

from pathlib import Path

from aip.config import read_config
from aip.engine import run_health, run_setup
from aip.github.fake import FakeGitHub

CONFIG_A = """\
standard_version: 1
roles:
  architect_reviewer:
    agent: opus
  developer:
    agent: codex
github:
  project: true
workflow:
  independent_review_required: true
"""

CONFIG_B = """\
standard_version: 1
roles:
  architect_reviewer:
    agent: codex
  developer:
    agent: opus
github:
  project: true
workflow:
  independent_review_required: true
"""

SELF_ACCEPTED = (
    "review_status: TECHNICALLY ACCEPTED\n"
    "implementer: Developer\nacceptor: Developer\n"
    "build_slice: B1\ncurrent_actor: Developer\nnext_actor: Reviewer\n"
    "open_human_decisions: []\n"
)
INDEPENDENTLY_ACCEPTED = (
    "review_status: TECHNICALLY ACCEPTED\n"
    "implementer: Developer\nacceptor: Reviewer\n"
    "build_slice: B1\ncurrent_actor: Reviewer\nnext_actor: Human\n"
    "open_human_decisions: []\n"
)


def test_config_agents_are_swappable(tmp_path: Path):
    (tmp_path / ".aip").mkdir()
    (tmp_path / ".aip/config.yml").write_text(CONFIG_A)
    a = read_config(tmp_path)
    assert a.architect_reviewer_agent == "opus" and a.developer_agent == "codex"

    (tmp_path / ".aip/config.yml").write_text(CONFIG_B)
    b = read_config(tmp_path)
    assert b.architect_reviewer_agent == "codex" and b.developer_agent == "opus"


def _health_after(tmp_path: Path, config: str, status_yml: str):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    (tmp_path / ".aip/config.yml").write_text(config)
    (tmp_path / "docs/status/current.yml").write_text(status_yml)
    return run_health(tmp_path, client, "acme", "widget")


def test_invariant_fails_for_self_acceptance_in_both_configs(tmp_path: Path):
    for config in (CONFIG_A, CONFIG_B):
        health = _health_after(tmp_path, config, SELF_ACCEPTED)
        inv = next(c for c in health.checks if c.key == "independent_review")
        assert inv.status.name == "MISSING", config


def test_invariant_passes_for_independent_acceptance_in_both_configs(tmp_path: Path):
    for config in (CONFIG_A, CONFIG_B):
        health = _health_after(tmp_path, config, INDEPENDENTLY_ACCEPTED)
        inv = next(c for c in health.checks if c.key == "independent_review")
        assert inv.status.name == "PRESENT", config
