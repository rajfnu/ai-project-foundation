"""`aip sync` projects the repository's current status into the GitHub Project item.

The repository (docs/status/current.yml) is the source of truth; sync pushes it one-way
into the Project so the board is a live projection, never a second source of truth.
"""

from pathlib import Path

from aip.engine import run_setup, run_sync
from aip.github.fake import FakeGitHub
from aip.standard import project_title

STATUS_YML = (
    "status: Implementing\n"
    "build_slice: Build 005A\n"
    "current_actor: Developer\n"
    "next_actor: Reviewer\n"
    "review_status: CHECK\n"
    "priority: P1\n"
    "customer_ready: No\n"
    "implementer: Developer\nacceptor: null\nopen_human_decisions: []\n"
)


def _setup(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    return client


def _project_id(client):
    return client.find_project("acme", project_title("widget")).id


def test_sync_creates_item_and_sets_field_values(tmp_path: Path):
    client = _setup(tmp_path)
    (tmp_path / "docs/status/current.yml").write_text(STATUS_YML)

    report = run_sync(tmp_path, client, "acme", "widget")

    assert report.created is True
    assert report.item_title == "Build 005A"
    items = client.list_items(_project_id(client))
    assert len(items) == 1
    values = items[0].values
    assert values["Status"] == "Implementing"
    assert values["Build / Slice"] == "Build 005A"
    assert values["Current Actor"] == "Developer"
    assert values["Next Actor"] == "Reviewer"
    assert values["Review Status"] == "CHECK"
    assert values["Priority"] == "P1"


def test_sync_is_idempotent_no_duplicate_item(tmp_path: Path):
    client = _setup(tmp_path)
    (tmp_path / "docs/status/current.yml").write_text(STATUS_YML)
    run_sync(tmp_path, client, "acme", "widget")

    second = run_sync(tmp_path, client, "acme", "widget")

    assert second.created is False
    assert len(client.list_items(_project_id(client))) == 1


def test_sync_updates_changed_values_in_place(tmp_path: Path):
    client = _setup(tmp_path)
    (tmp_path / "docs/status/current.yml").write_text(STATUS_YML)
    run_sync(tmp_path, client, "acme", "widget")

    # slice advances: review passed
    (tmp_path / "docs/status/current.yml").write_text(
        STATUS_YML.replace("status: Implementing", "status: Review").replace(
            "review_status: CHECK", "review_status: TECHNICALLY ACCEPTED"
        )
    )
    run_sync(tmp_path, client, "acme", "widget")

    items = client.list_items(_project_id(client))
    assert len(items) == 1
    assert items[0].values["Status"] == "Review"
    assert items[0].values["Review Status"] == "TECHNICALLY ACCEPTED"


def test_sync_skips_null_values(tmp_path: Path):
    client = _setup(tmp_path)
    (tmp_path / "docs/status/current.yml").write_text(
        "status: null\nbuild_slice: Build 1\ncurrent_actor: Developer\n"
        "next_actor: null\nreview_status: null\npriority: null\ncustomer_ready: null\n"
        "open_human_decisions: []\n"
    )

    report = run_sync(tmp_path, client, "acme", "widget")

    assert "Current Actor" in report.fields_set
    assert "Status" not in report.fields_set  # null not pushed


def test_greenfield_setup_creates_no_placeholder_item(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    report = run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    assert report.sync is None
    assert client.list_items(_project_id(client)) == []


def test_setup_projects_slice_when_status_has_one(tmp_path: Path):
    client = FakeGitHub("acme", "widget")
    run_setup(tmp_path, client, "acme", "widget", dry_run=False)
    (tmp_path / "docs/status/current.yml").write_text(STATUS_YML)

    report = run_setup(tmp_path, client, "acme", "widget", dry_run=False)

    assert report.sync is not None and report.sync.item_title == "Build 005A"
    assert len(client.list_items(_project_id(client))) == 1


def test_sync_coerces_yaml_boolean_back_to_option_name(tmp_path: Path):
    """YAML parses `No`/`Yes` as booleans; sync must map them back to option names
    (e.g. Customer Ready: No) rather than pushing 'False'/'True'."""
    client = _setup(tmp_path)
    (tmp_path / "docs/status/current.yml").write_text(
        "build_slice: Build 1\ncustomer_ready: No\ncurrent_actor: Developer\n"
        "open_human_decisions: []\n"
    )

    report = run_sync(tmp_path, client, "acme", "widget")

    assert report.fields_set["Customer Ready"] == "No"
    items = client.list_items(_project_id(client))
    assert items[0].values["Customer Ready"] == "No"
