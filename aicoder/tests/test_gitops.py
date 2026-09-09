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
