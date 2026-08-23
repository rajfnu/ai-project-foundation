from pathlib import Path

from aip.apply import apply_actions
from aip.plan import plan_file_actions


def test_human_agents_content_preserved_and_block_appended(tmp_path: Path):
    human = "# My project rules\n\nAlways do the thing.\n"
    (tmp_path / "AGENTS.md").write_text(human)

    apply_actions(tmp_path, plan_file_actions(tmp_path))

    result = (tmp_path / "AGENTS.md").read_text()
    assert "# My project rules" in result
    assert "Always do the thing." in result
    assert "AIP:BEGIN" in result and "AIP:END" in result


def test_managed_update_is_idempotent(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Mine\n")
    apply_actions(tmp_path, plan_file_actions(tmp_path))
    first = (tmp_path / "AGENTS.md").read_text()

    # second full cycle must not change the file or plan another managed update
    remaining = [a for a in plan_file_actions(tmp_path) if a.key == "AGENTS.md"]
    assert remaining == []
    apply_actions(tmp_path, plan_file_actions(tmp_path))
    assert (tmp_path / "AGENTS.md").read_text() == first
