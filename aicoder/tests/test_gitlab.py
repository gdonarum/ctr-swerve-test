import pytest

from aicoder import gitlab
from aicoder.config import Config


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


@pytest.fixture
def patch_request(monkeypatch):
    """Patch gitlab.requests.request and capture the calls."""
    calls = []

    def make(response):
        def fake(method, url, **kwargs):
            calls.append({"method": method, "url": url, **kwargs})
            return response
        monkeypatch.setattr(gitlab.requests, "request", fake)
        return calls

    return make


def test_not_configured():
    cfg = Config()
    with pytest.raises(gitlab.GitLabError, match="not configured"):
        gitlab.list_issues(cfg)


def test_no_project():
    cfg = Config(gitlab_url="https://gl.test", gitlab_token="t")
    with pytest.raises(gitlab.GitLabError, match="No GitLab project"):
        gitlab.list_issues(cfg)


def test_list_issues(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data=[{"iid": 1, "state": "opened", "title": "Bug"}]))
    issues = gitlab.list_issues(gitlab_config, state="opened")
    assert issues[0]["title"] == "Bug"
    # project path is URL-encoded
    assert "group%2Fproject" in calls[0]["url"]
    assert calls[0]["params"]["state"] == "opened"


def test_list_issues_all_state_omits_param(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data=[]))
    gitlab.list_issues(gitlab_config, state="all")
    assert "state" not in calls[0]["params"]


def test_get_issue(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data={"iid": 7, "title": "T", "state": "opened"}))
    issue = gitlab.get_issue(gitlab_config, 7)
    assert issue["iid"] == 7
    assert calls[0]["url"].endswith("/issues/7")


def test_create_issue(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data={"iid": 9, "web_url": "https://gl.test/x/9"}))
    issue = gitlab.create_issue(gitlab_config, "New bug", "details", labels=["bug", "urgent"])
    assert issue["iid"] == 9
    assert calls[0]["method"] == "POST"
    assert calls[0]["data"]["title"] == "New bug"
    assert calls[0]["data"]["labels"] == "bug,urgent"


def test_create_issue_requires_title(gitlab_config, patch_request):
    patch_request(FakeResponse(json_data={}))
    with pytest.raises(gitlab.GitLabError, match="title is required"):
        gitlab.create_issue(gitlab_config, "  ")


def test_auth_error(patch_request, gitlab_config):
    patch_request(FakeResponse(status_code=401, text="unauthorized"))
    with pytest.raises(gitlab.GitLabError, match="authentication failed"):
        gitlab.list_issues(gitlab_config)


def test_not_found(patch_request, gitlab_config):
    patch_request(FakeResponse(status_code=404, text="nope"))
    with pytest.raises(gitlab.GitLabError, match="not found"):
        gitlab.get_issue(gitlab_config, 123)


def test_explicit_project_overrides_default(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data=[]))
    gitlab.list_issues(gitlab_config, project="other/repo")
    assert "other%2Frepo" in calls[0]["url"]


def test_format_helpers():
    short = gitlab.format_issue_short({"iid": 3, "state": "opened", "title": "Hi"})
    assert short == "#3 [opened] Hi"
    detail = gitlab.format_issue_detail(
        {"iid": 3, "title": "Hi", "state": "opened", "author": {"name": "Ann"},
         "labels": ["a"], "web_url": "u", "description": "body"}
    )
    assert "Ann" in detail and "body" in detail
