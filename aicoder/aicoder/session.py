"""Save and resume conversations.

A session is the message history plus a little metadata (model, working
directory), stored as JSON. Everything aicoder puts in ``agent.messages`` is
already plain dicts and strings, so it serializes directly.

Sessions live under ``AICODER_SESSIONS_DIR`` if set, otherwise
``~/.aicoder/sessions``.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SessionError(Exception):
    """A user-facing error saving or loading a session."""


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sessions_dir() -> Path:
    override = os.environ.get("AICODER_SESSIONS_DIR")
    base = Path(override) if override else Path.home() / ".aicoder" / "sessions"
    return base


def _sanitize(name: str) -> str:
    cleaned = _SAFE_NAME.sub("-", name.strip()).strip("-")
    if not cleaned:
        raise SessionError("Invalid session name.")
    return cleaned


def _path(name: str) -> Path:
    return sessions_dir() / f"{_sanitize(name)}.json"


def default_name() -> str:
    """A timestamp-based name for when the user doesn't give one."""
    return time.strftime("session-%Y%m%d-%H%M%S")


def save(
    messages: List[Dict[str, Any]],
    model: Optional[str],
    workdir: str,
    name: Optional[str] = None,
) -> str:
    """Persist a session and return the name it was saved under."""
    name = name or default_name()
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model,
        "workdir": workdir,
        "messages": messages,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise SessionError(f"Could not write session: {exc}") from exc
    return _sanitize(name)


def load(name: str) -> Dict[str, Any]:
    """Load a saved session's payload dict."""
    path = _path(name)
    if not path.is_file():
        raise SessionError(f"No saved session named {name!r}. Try /sessions.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"Could not read session {name!r}: {exc}") from exc
    if not isinstance(data.get("messages"), list):
        raise SessionError(f"Session {name!r} is missing a message history.")
    return data


def list_sessions() -> List[str]:
    """Return saved session names, newest first."""
    directory = sessions_dir()
    if not directory.is_dir():
        return []
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files]


def delete(name: str) -> None:
    path = _path(name)
    if not path.is_file():
        raise SessionError(f"No saved session named {name!r}.")
    path.unlink()
