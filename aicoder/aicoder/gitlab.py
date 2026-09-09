"""Minimal client for an on-prem GitLab instance (REST API v4).

Covers the issue-tracking workflow aicoder needs: list, get, and create issues.
Credentials come from the environment (``GITLAB_URL``, ``GITLAB_TOKEN``); the
project is supplied per call (falling back to ``GITLAB_PROJECT`` if set).

The project identifier may be a numeric id or a ``group/subgroup/project`` path;
paths are URL-encoded as GitLab requires.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from aicoder.config import Config

DEFAULT_TIMEOUT = 30


class GitLabError(Exception):
    """A user-facing error talking to GitLab (config, network, or API)."""


def _require_config(config: Config) -> None:
    if not config.has_gitlab_credentials():
        raise GitLabError(
            "GitLab is not configured. Set GITLAB_URL and GITLAB_TOKEN."
        )


def _resolve_project(config: Config, project: Optional[str]) -> str:
    project = project or config.gitlab_project
    if not project:
        raise GitLabError(
            "No GitLab project given. Pass a project id or 'group/path', "
            "or set GITLAB_PROJECT."
        )
    return quote(str(project), safe="")


def _base(config: Config) -> str:
    return config.gitlab_url.rstrip("/") + "/api/v4"


def _headers(config: Config) -> Dict[str, str]:
    return {"PRIVATE-TOKEN": config.gitlab_token}


def _request(config: Config, method: str, path: str, **kwargs) -> Any:
    url = f"{_base(config)}{path}"
    try:
        resp = requests.request(
            method, url, headers=_headers(config), timeout=DEFAULT_TIMEOUT, **kwargs
        )
    except requests.RequestException as exc:
        raise GitLabError(f"Network error contacting GitLab: {exc}") from exc
    if resp.status_code == 401:
        raise GitLabError("GitLab authentication failed. Check GITLAB_TOKEN.")
    if resp.status_code == 404:
        raise GitLabError("GitLab resource not found (check the project or issue id).")
    if not resp.ok:
        raise GitLabError(f"GitLab API error {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError:
        raise GitLabError("GitLab returned a non-JSON response.")


def list_issues(
    config: Config,
    project: Optional[str] = None,
    state: str = "opened",
    search: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List issues in a project. ``state`` is opened|closed|all."""
    _require_config(config)
    pid = _resolve_project(config, project)
    params: Dict[str, Any] = {"per_page": max(1, min(limit, 100))}
    if state and state != "all":
        params["state"] = state
    if search:
        params["search"] = search
    data = _request(config, "GET", f"/projects/{pid}/issues", params=params)
    return data if isinstance(data, list) else []


def get_issue(config: Config, issue_iid: int, project: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a single issue by its project-scoped internal id (iid)."""
    _require_config(config)
    pid = _resolve_project(config, project)
    return _request(config, "GET", f"/projects/{pid}/issues/{int(issue_iid)}")


def create_issue(
    config: Config,
    title: str,
    description: str = "",
    project: Optional[str] = None,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new issue and return the created object."""
    _require_config(config)
    if not title.strip():
        raise GitLabError("An issue title is required.")
    pid = _resolve_project(config, project)
    payload: Dict[str, Any] = {"title": title, "description": description}
    if labels:
        payload["labels"] = ",".join(labels)
    return _request(config, "POST", f"/projects/{pid}/issues", data=payload)


def format_issue_short(issue: Dict[str, Any]) -> str:
    """One-line summary of an issue for lists."""
    iid = issue.get("iid", "?")
    state = issue.get("state", "?")
    title = issue.get("title", "")
    return f"#{iid} [{state}] {title}"


def format_issue_detail(issue: Dict[str, Any]) -> str:
    """Multi-line detail view of a single issue."""
    lines = [
        f"#{issue.get('iid', '?')}: {issue.get('title', '')}",
        f"state:   {issue.get('state', '?')}",
        f"author:  {(issue.get('author') or {}).get('name', '?')}",
        f"labels:  {', '.join(issue.get('labels') or []) or '(none)'}",
        f"url:     {issue.get('web_url', '')}",
        "",
        (issue.get("description") or "(no description)"),
    ]
    return "\n".join(lines)
