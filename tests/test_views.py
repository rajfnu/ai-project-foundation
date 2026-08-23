"""GitHub Project views: created and configured via the API to the extent supported.

Layout, filter, and visible fields are automated; grouping is not exposed by the API
(a Board layout auto-groups by Status). Views are created once and not re-reconciled, so
human tweaks to a view are not overwritten on re-run.
"""

from aip.audit import Status
from aip.github.apply import apply_github_actions
from aip.github.audit import audit_github
from aip.github.fake import FakeGitHub
from aip.github.plan import plan_github_actions
from aip.standard import REQUIRED_VIEWS, project_title


def _converge(client):
    apply_github_actions(client, "acme", "widget", plan_github_actions(client, "acme", "widget"))


def test_views_missing_then_present():
    client = FakeGitHub("acme", "widget")
    findings = {f.key: f for f in audit_github(client, "acme", "widget")}
    for v in REQUIRED_VIEWS:
        assert findings[f"view:{v.name}"].status is Status.MISSING

    _converge(client)

    findings = {f.key: f for f in audit_github(client, "acme", "widget")}
    for v in REQUIRED_VIEWS:
        assert findings[f"view:{v.name}"].status is Status.PRESENT


def test_views_idempotent_no_duplicates():
    client = FakeGitHub("acme", "widget")
    _converge(client)

    assert plan_github_actions(client, "acme", "widget") == []
    pid = client.find_project("acme", project_title("widget")).id
    names = [v.name for v in client.list_views(pid)]
    assert names.count("Delivery Board") == 1
    assert names.count("Current Work") == 1


def test_current_work_view_is_configured():
    client = FakeGitHub("acme", "widget")
    _converge(client)
    pid = client.find_project("acme", project_title("widget")).id

    view = next(v for v in client.list_views(pid) if v.name == "Current Work")
    assert view.layout == "TABLE_LAYOUT"
    assert view.filter == "-status:Done,Accepted"
    assert len(view.visible_field_ids) == 5  # the five configured columns


def test_delivery_board_is_board_layout():
    client = FakeGitHub("acme", "widget")
    _converge(client)
    pid = client.find_project("acme", project_title("widget")).id

    board = next(v for v in client.list_views(pid) if v.name == "Delivery Board")
    assert board.layout == "BOARD_LAYOUT"
