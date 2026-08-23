from pathlib import Path

from aip.apply import apply_actions
from aip.audit import Status, audit_files
from aip.plan import ActionKind, plan_file_actions
from aip.standard import REQUIRED_PATHS


def test_greenfield_plans_action_per_missing_path(tmp_path: Path):
    actions = plan_file_actions(tmp_path)
    assert {a.key for a in actions} == {r.key for r in REQUIRED_PATHS}


def test_apply_then_reaudit_all_present(tmp_path: Path):
    apply_actions(tmp_path, plan_file_actions(tmp_path))

    findings = audit_files(tmp_path)
    assert all(f.status is Status.PRESENT for f in findings), [
        f.key for f in findings if f.status is not Status.PRESENT
    ]


def test_idempotent_second_plan_is_empty(tmp_path: Path):
    apply_actions(tmp_path, plan_file_actions(tmp_path))
    assert plan_file_actions(tmp_path) == []


def test_created_config_and_agents_have_content(tmp_path: Path):
    apply_actions(tmp_path, plan_file_actions(tmp_path))

    agents = (tmp_path / "AGENTS.md").read_text()
    assert "AIP:BEGIN" in agents and "AIP:END" in agents
    config = (tmp_path / ".aip/config.yml").read_text()
    assert "standard_version" in config


def test_managed_file_present_plans_managed_update_not_overwrite(tmp_path: Path):
    # human wrote their own AGENTS.md without the managed block
    (tmp_path / "AGENTS.md").write_text("# My project rules\nDo the thing.\n")

    actions = {a.key: a for a in plan_file_actions(tmp_path)}
    assert actions["AGENTS.md"].kind is ActionKind.UPDATE_MANAGED_BLOCK
