import json

from aip.github.gh import GhGitHub


class RecordingRunner:
    """Fake subprocess runner: returns canned stdout per command, records calls."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, args, stdin):
        self.calls.append(args)
        for matcher, out in self.responses:
            if matcher(args):
                return out
        return ""


def test_find_project_matches_by_title():
    runner = RecordingRunner(
        [(
            lambda a: a[:3] == ["gh", "project", "list"],
            json.dumps({"projects": [
                {"id": "PVT_x", "number": 7, "title": "AIP · widget"},
                {"id": "PVT_y", "number": 8, "title": "Other"},
            ]}),
        )]
    )
    client = GhGitHub(runner=runner)

    project = client.find_project("acme", "AIP · widget")
    assert project is not None and project.id == "PVT_x" and project.number == 7


def test_find_project_returns_none_when_absent():
    runner = RecordingRunner(
        [(lambda a: True, json.dumps({"projects": []}))]
    )
    assert GhGitHub(runner=runner).find_project("acme", "AIP · widget") is None


def test_create_label_invokes_gh_label_create():
    runner = RecordingRunner([(lambda a: True, "")])
    GhGitHub(runner=runner).create_label("acme/widget", "aip:blocked", "b60205", "Work is blocked")

    call = runner.calls[0]
    assert call[:3] == ["gh", "label", "create"]
    assert "aip:blocked" in call
    assert "--repo" in call and "acme/widget" in call


def test_create_single_select_field_inlines_options_in_query():
    captured = {}

    def runner(args, stdin):
        captured["args"] = args
        return json.dumps(
            {"data": {"createProjectV2Field": {"projectV2Field": {
                "id": "F1", "name": "Status", "dataType": "SINGLE_SELECT"}}}}
        )

    field = GhGitHub(runner=runner).create_field("PVT_1", "Status", "SINGLE_SELECT", ["Backlog", "Done"])

    assert field.id == "F1"
    query = next(a for a in captured["args"] if a.startswith("query="))
    # options must be inlined as GraphQL literals, not passed as a JSON string variable
    assert "Backlog" in query and "Done" in query
    assert not any(a.startswith("o=") for a in captured["args"])


def test_create_text_field_has_no_options():
    captured = {}

    def runner(args, stdin):
        captured["args"] = args
        return json.dumps(
            {"data": {"createProjectV2Field": {"projectV2Field": {
                "id": "F2", "name": "Build / Slice", "dataType": "TEXT"}}}}
        )

    GhGitHub(runner=runner).create_field("PVT_1", "Build / Slice", "TEXT", [])

    query = next(a for a in captured["args"] if a.startswith("query="))
    assert "singleSelectOptions" not in query


def _options_query_response(options):
    return json.dumps({"data": {"node": {"fields": {"nodes": [
        {"id": "FLD_1", "options": [{"name": n, "color": c} for n, c in options]},
    ]}}}})


def _update_response():
    return json.dumps({"data": {"updateProjectV2Field": {"projectV2Field": {"id": "FLD_1", "name": "Status"}}}})


def test_add_field_options_replaces_github_default_status():
    # a fresh project's built-in Status has exactly Todo/In Progress/Done — safe to replace
    runner = RecordingRunner([
        (lambda a: "fields(first" in _query(a), _options_query_response(
            [("Todo", "GRAY"), ("In Progress", "YELLOW"), ("Done", "GREEN")])),
        (lambda a: "updateProjectV2Field" in _query(a), _update_response()),
    ])
    GhGitHub(runner=runner).add_field_options("PVT_x", "FLD_1", ["Backlog", "Implementing"])

    update = next(_query(a) for a in runner.calls if "updateProjectV2Field" in _query(a))
    assert "Backlog" in update and "Implementing" in update
    assert "Todo" not in update  # defaults replaced, not kept


def test_add_field_options_preserves_existing_custom_options():
    runner = RecordingRunner([
        (lambda a: "fields(first" in _query(a), _options_query_response([("Spike", "BLUE")])),
        (lambda a: "updateProjectV2Field" in _query(a), _update_response()),
    ])
    GhGitHub(runner=runner).add_field_options("PVT_x", "FLD_1", ["Backlog"])

    update = next(_query(a) for a in runner.calls if "updateProjectV2Field" in _query(a))
    assert "Spike" in update and "Backlog" in update  # custom option preserved, new one added


def _query(args):
    for a in args:
        if a.startswith("query="):
            return a
    return ""
