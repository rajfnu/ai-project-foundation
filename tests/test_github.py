from aip.audit import Status
from aip.github.apply import apply_github_actions
from aip.github.audit import audit_github
from aip.github.fake import FakeGitHub
from aip.github.plan import plan_github_actions
from aip.standard import REQUIRED_FIELDS


def make_client():
    return FakeGitHub(owner="acme", repo="widget")


def test_no_project_reports_project_and_fields_missing():
    client = make_client()

    findings = {f.key: f for f in audit_github(client, "acme", "widget")}

    assert findings["github_project"].status is Status.MISSING
    for field in REQUIRED_FIELDS:
        assert findings[f"field:{field.name}"].status is Status.MISSING


def test_setup_creates_project_and_all_fields():
    client = make_client()

    apply_github_actions(client, "acme", "widget", plan_github_actions(client, "acme", "widget"))

    findings = {f.key: f for f in audit_github(client, "acme", "widget")}
    assert findings["github_project"].status is Status.PRESENT
    for field in REQUIRED_FIELDS:
        assert findings[f"field:{field.name}"].status is Status.PRESENT


def test_github_setup_is_idempotent():
    client = make_client()
    apply_github_actions(client, "acme", "widget", plan_github_actions(client, "acme", "widget"))

    second = plan_github_actions(client, "acme", "widget")
    assert second == []

    # and no duplicate project was created
    assert len(client.projects_for("acme")) == 1


def test_existing_project_is_adopted_not_recreated():
    client = make_client()
    from aip.standard import project_title

    existing = client.create_project("acme", project_title("widget"))

    actions = plan_github_actions(client, "acme", "widget")
    # should not plan to create another project
    assert all(a.kind.name != "CREATE_PROJECT" for a in actions)

    apply_github_actions(client, "acme", "widget", actions)
    projects = client.projects_for("acme")
    assert len(projects) == 1 and projects[0].id == existing.id
