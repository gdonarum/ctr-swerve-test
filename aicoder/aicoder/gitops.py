"""Thin, safe wrappers around the local ``git`` CLI.

Everything runs inside the configured working directory. Functions raise
``GitError`` (with the git stderr) on failure so callers can surface a clean
message instead of a stack trace.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional

from aicoder.config import Config


class GitError(Exception):
    """A git command failed or git is unavailable."""


def _run(config: Config, args: List[str], timeout: int = 60) -> str:
    if shutil.which("git") is None:
        raise GitError("git is not installed or not on PATH.")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=config.workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise GitError(f"git {' '.join(args)} timed out.")
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise GitError(message or f"git {' '.join(args)} failed.")
    return result.stdout


def is_repo(config: Config) -> bool:
    try:
        out = _run(config, ["rev-parse", "--is-inside-work-tree"])
    except GitError:
        return False
    return out.strip() == "true"


def _require_repo(config: Config) -> None:
    if not is_repo(config):
        raise GitError("Not inside a git repository.")


def status(config: Config) -> str:
    _require_repo(config)
    changes = _run(config, ["status", "--short"]).rstrip()
    if not changes:
        return "(clean working tree)"
    return _run(config, ["status", "--short", "--branch"]).rstrip()


def diff(config: Config, staged: bool = False, path: Optional[str] = None) -> str:
    _require_repo(config)
    args = ["diff"]
    if staged:
        args.append("--staged")
    if path:
        args += ["--", path]
    out = _run(config, args).rstrip()
    return out or "(no changes)"


def add(config: Config, paths: List[str]) -> str:
    _require_repo(config)
    if not paths:
        raise GitError("No paths given to stage.")
    _run(config, ["add", "--", *paths])
    return f"Staged: {', '.join(paths)}"


def commit(config: Config, message: str, add_all: bool = False) -> str:
    _require_repo(config)
    if not message.strip():
        raise GitError("A commit message is required.")
    args = ["commit", "-m", message]
    if add_all:
        args.insert(1, "-a")
    out = _run(config, args)
    return out.strip() or "Committed."


def log(config: Config, count: int = 10) -> str:
    _require_repo(config)
    out = _run(config, ["log", f"-{max(1, count)}", "--oneline", "--decorate"]).rstrip()
    return out or "(no commits yet)"


def current_branch(config: Config) -> str:
    _require_repo(config)
    return _run(config, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
