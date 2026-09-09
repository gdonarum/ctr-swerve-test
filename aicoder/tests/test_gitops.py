import os

import pytest

from aicoder import gitops
from aicoder.config import Config


def _write(config, name, content):
    with open(os.path.join(config.workdir, name), "w") as f:
        f.write(content)


def test_not_a_repo(tmp_path):
    cfg = Config(workdir=str(tmp_path))
    assert gitops.is_repo(cfg) is False
    with pytest.raises(gitops.GitError, match="Not inside a git repository"):
        gitops.status(cfg)


def test_status_add_commit_log(git_repo):
    assert gitops.is_repo(git_repo)
    _write(git_repo, "hello.txt", "hi\n")

    status = gitops.status(git_repo)
    assert "hello.txt" in status

    assert "Staged" in gitops.add(git_repo, ["hello.txt"])
    gitops.commit(git_repo, "add hello")

    log = gitops.log(git_repo)
    assert "add hello" in log
    assert gitops.status(git_repo) == "(clean working tree)"


def test_commit_requires_message(git_repo):
    _write(git_repo, "a.txt", "x")
    gitops.add(git_repo, ["a.txt"])
    with pytest.raises(gitops.GitError, match="message is required"):
        gitops.commit(git_repo, "   ")


def test_commit_all(git_repo):
    _write(git_repo, "a.txt", "x")
    gitops.add(git_repo, ["a.txt"])
    gitops.commit(git_repo, "initial")
    _write(git_repo, "a.txt", "changed")
    gitops.commit(git_repo, "update", add_all=True)
    assert "update" in gitops.log(git_repo)


def test_diff(git_repo):
    _write(git_repo, "a.txt", "one\n")
    gitops.add(git_repo, ["a.txt"])
    gitops.commit(git_repo, "init")
    _write(git_repo, "a.txt", "two\n")
    diff = gitops.diff(git_repo)
    assert "-one" in diff and "+two" in diff


def test_add_nothing(git_repo):
    with pytest.raises(gitops.GitError, match="No paths"):
        gitops.add(git_repo, [])


import subprocess


@pytest.mark.parametrize("url,expected", [
    ("git@gitlab.example.com:group/project.git", "group/project"),
    ("git@gitlab.example.com:group/sub/project.git", "group/sub/project"),
    ("https://gitlab.example.com/group/project.git", "group/project"),
    ("https://gitlab.example.com/group/sub/project", "group/sub/project"),
    ("ssh://git@gitlab.example.com:22/group/project.git", "group/project"),
    ("https://gitlab.example.com/group/project/", "group/project"),
    ("", None),
])
def test_project_path_from_url(url, expected):
    assert gitops.project_path_from_url(url) == expected


def test_remote_url(git_repo):
    subprocess.run(
        ["git", "remote", "add", "origin", "git@gitlab.test:grp/proj.git"],
        cwd=git_repo.workdir, check=True, capture_output=True,
    )
    assert gitops.remote_url(git_repo) == "git@gitlab.test:grp/proj.git"


def test_remote_url_missing(git_repo):
    with pytest.raises(gitops.GitError):
        gitops.remote_url(git_repo)
