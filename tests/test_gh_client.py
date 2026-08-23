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


def test_add_field_options_reports_api_limitation():
    client = GhGitHub(runner=RecordingRunner([]))
    try:
        client.add_field_options("PVT_x", "FLD_1", ["New Option"])
        assert False, "expected NotImplementedError"
    except NotImplementedError as exc:
        assert "New Option" in str(exc)
