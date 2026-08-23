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


def _balanced(q: str) -> bool:
    depth = {"{": 0, "(": 0}
    pairs = {"}": "{", ")": "("}
    for ch in q:
        if ch in depth:
            depth[ch] += 1
        elif ch in pairs:
            depth[pairs[ch]] -= 1
            if depth[pairs[ch]] < 0:
                return False
    return depth["{"] == 0 and depth["("] == 0


def test_all_graphql_queries_are_brace_balanced():
    from aip.github.client import Field
    runner = RecordingRunner([(lambda a: True, json.dumps({"data": {
        "node": {"fields": {"nodes": [{"id": "F_sel", "options": [{"id": "O1", "name": "X"}]}]}},
        "createProjectV2Field": {"projectV2Field": {"id": "F", "name": "N", "dataType": "TEXT"}},
        "updateProjectV2Field": {"projectV2Field": {"id": "F", "name": "N"}},
        "addProjectV2DraftIssue": {"projectItem": {"id": "I"}},
        "updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "I"}},
    }}))])
    c = GhGitHub(runner=runner)
    c.create_field("P", "Status", "SINGLE_SELECT", ["A", "B"])
    c.create_field("P", "Slice", "TEXT", [])
    c.add_draft_item("P", "S1")
    c.set_field_value("P", "I", Field("F_sel", "Status", "SINGLE_SELECT", ["X"]), "X")
    c.set_field_value("P", "I", Field("F_txt", "Slice", "TEXT", []), "v")
    for call in runner.calls:
        q = _query(call)
        if q:
            assert _balanced(q), q


def test_add_draft_item_uses_draft_issue_mutation():
    runner = RecordingRunner([(lambda a: True, json.dumps(
        {"data": {"addProjectV2DraftIssue": {"projectItem": {"id": "ITM_1"}}}}))])
    item = GhGitHub(runner=runner).add_draft_item("PVT_1", "Build 005A")
    assert item.id == "ITM_1" and item.title == "Build 005A"
    assert "addProjectV2DraftIssue" in _query(runner.calls[0])


def test_set_field_value_text_uses_text_value():
    from aip.github.client import Field
    runner = RecordingRunner([(lambda a: True, json.dumps(
        {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITM_1"}}}}))])
    GhGitHub(runner=runner).set_field_value(
        "PVT_1", "ITM_1", Field("F_txt", "Build / Slice", "TEXT", []), "Build 005A")
    q = _query(runner.calls[0])
    assert "updateProjectV2ItemFieldValue" in q and "text:" in q


def test_set_field_value_single_select_resolves_option_id():
    from aip.github.client import Field
    runner = RecordingRunner([
        (lambda a: "options{id name}" in _query(a) or "options{name id}" in _query(a) or "options" in _query(a) and "fields(first" in _query(a),
         json.dumps({"data": {"node": {"fields": {"nodes": [
             {"id": "F_sel", "options": [{"id": "OPT_impl", "name": "Implementing"}]}]}}}})),
        (lambda a: "updateProjectV2ItemFieldValue" in _query(a),
         json.dumps({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITM_1"}}}})),
    ])
    GhGitHub(runner=runner).set_field_value(
        "PVT_1", "ITM_1", Field("F_sel", "Status", "SINGLE_SELECT", ["Implementing"]), "Implementing")
    update = next(_query(a) for a in runner.calls if "updateProjectV2ItemFieldValue" in _query(a))
    assert "singleSelectOptionId" in update
    assert any("OPT_impl" in str(a) for a in runner.calls)


def test_create_view_uses_create_mutation_with_layout():
    runner = RecordingRunner([(lambda a: True, json.dumps(
        {"data": {"createProjectV2View": {"projectV2View": {
            "id": "V1", "name": "Delivery Board", "layout": "BOARD_LAYOUT"}}}}))])
    view = GhGitHub(runner=runner).create_view("PVT_1", "Delivery Board", "BOARD_LAYOUT")
    assert view.id == "V1" and view.layout == "BOARD_LAYOUT"
    q = _query(runner.calls[0])
    assert "createProjectV2View" in q and "BOARD_LAYOUT" in q
    assert _balanced(q)


def test_update_view_sets_filter_and_visible_fields():
    runner = RecordingRunner([(lambda a: True, json.dumps(
        {"data": {"updateProjectV2View": {"projectV2View": {"id": "V1"}}}}))])
    GhGitHub(runner=runner).update_view("PVT_1", "V1", "-status:Done", ["F_a", "F_b"])
    q = _query(runner.calls[0])
    assert "updateProjectV2View" in q and "visibleFieldIds" in q
    assert "F_a" in q and "F_b" in q
    assert _balanced(q)


def test_list_views_parses_nodes():
    runner = RecordingRunner([(lambda a: True, json.dumps(
        {"data": {"node": {"views": {"nodes": [
            {"id": "V1", "name": "Delivery Board", "layout": "BOARD_LAYOUT"}]}}}}))])
    views = GhGitHub(runner=runner).list_views("PVT_1")
    assert len(views) == 1 and views[0].name == "Delivery Board"
