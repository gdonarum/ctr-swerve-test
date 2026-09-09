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


# --- merge requests ---------------------------------------------------------


def test_list_merge_requests(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data=[
        {"iid": 2, "state": "opened", "source_branch": "f", "target_branch": "main", "title": "MR"}
    ]))
    mrs = gitlab.list_merge_requests(gitlab_config)
    assert mrs[0]["title"] == "MR"
    assert "merge_requests" in calls[0]["url"]
    assert calls[0]["params"]["state"] == "opened"


def test_get_merge_request(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data={"iid": 5, "title": "T"}))
    mr = gitlab.get_merge_request(gitlab_config, 5)
    assert mr["iid"] == 5
    assert calls[0]["url"].endswith("/merge_requests/5")


def test_create_merge_request(patch_request, gitlab_config):
    calls = patch_request(FakeResponse(json_data={"iid": 3, "web_url": "https://gl.test/x/3"}))
    mr = gitlab.create_merge_request(
        gitlab_config, "feature", "main", "Add feature", description="d",
        remove_source_branch=True, labels=["x"],
    )
    assert mr["iid"] == 3
    assert calls[0]["method"] == "POST"
    assert calls[0]["data"]["source_branch"] == "feature"
    assert calls[0]["data"]["target_branch"] == "main"
    assert calls[0]["data"]["remove_source_branch"] is True
    assert calls[0]["data"]["labels"] == "x"


def test_create_mr_requires_branches(gitlab_config, patch_request):
    patch_request(FakeResponse(json_data={}))
    with pytest.raises(gitlab.GitLabError, match="source_branch and target_branch"):
        gitlab.create_merge_request(gitlab_config, "", "main", "T")


def test_create_mr_requires_title(gitlab_config, patch_request):
    patch_request(FakeResponse(json_data={}))
    with pytest.raises(gitlab.GitLabError, match="title is required"):
        gitlab.create_merge_request(gitlab_config, "f", "main", "  ")


def test_mr_format_helpers():
    short = gitlab.format_mr_short(
        {"iid": 4, "state": "opened", "source_branch": "f", "target_branch": "main", "title": "Hi"}
    )
    assert short == "!4 [opened] f→main  Hi"
    detail = gitlab.format_mr_detail(
        {"iid": 4, "title": "Hi", "state": "opened", "source_branch": "f",
         "target_branch": "main", "author": {"name": "Ann"}, "labels": [],
         "web_url": "u", "description": "body"}
    )
    assert "f → main" in detail and "body" in detail


def test_verify_passed_to_requests(monkeypatch, tmp_path):
    from aicoder.config import Config
    captured = {}

    def fake(method, url, **kwargs):
        captured.update(kwargs)
        return FakeResponse(json_data=[])

    monkeypatch.setattr(gitlab.requests, "request", fake)
    cfg = Config(gitlab_url="https://gl.test", gitlab_token="t", gitlab_project="g/p",
                 ca_bundle=str(tmp_path / "ca.pem"))
    gitlab.list_issues(cfg)
    assert captured["verify"] == str(tmp_path / "ca.pem")
