"""Shared pytest fixtures and lightweight fakes.

The fakes stand in for the OpenAI/LiteLLM client so the agent and CLI can be
tested without any network access.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from aicoder.config import Config


# --- Config fixtures --------------------------------------------------------


@pytest.fixture
def config(tmp_path):
    """A Config pointed at a temp working directory with LLM creds set."""
    return Config(
        base_url="https://litellm.test",
        api_key="sk-test",
        model="test-model",
        workdir=str(tmp_path),
    )


@pytest.fixture
def gitlab_config(tmp_path):
    return Config(
        workdir=str(tmp_path),
        gitlab_url="https://gitlab.test",
        gitlab_token="glpat-test",
        gitlab_project="group/project",
    )


@pytest.fixture
def git_repo(tmp_path):
    """Initialise a real git repo in a temp dir and return its Config."""
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test User")
    run("config", "commit.gpgsign", "false")
    return Config(workdir=str(tmp_path))


# --- Fake OpenAI-compatible client ------------------------------------------


def _chunk(content: Optional[str] = None, tool_calls: Optional[List[Any]] = None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=None)
    return SimpleNamespace(choices=[choice])


def text_chunks(text: str):
    """Stream a piece of assistant text as one or more chunks."""
    return [_chunk(content=text)]


def tool_call_chunks(index: int, call_id: str, name: str, arguments: str):
    """Stream a single tool call, fragmented across two chunks like the API."""
    part1 = SimpleNamespace(index=index, id=call_id, function=SimpleNamespace(name=name, arguments=""))
    part2 = SimpleNamespace(index=index, id=None, function=SimpleNamespace(name="", arguments=arguments))
    return [_chunk(tool_calls=[part1]), _chunk(tool_calls=[part2])]


class FakeCompletions:
    def __init__(self, scripted: List[List[Any]]):
        # scripted is a list of "responses"; each response is a list of chunks.
        self._scripted = list(scripted)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripted:
            raise AssertionError("FakeCompletions ran out of scripted responses")
        return iter(self._scripted.pop(0))


class FakeClient:
    """Mimics the parts of the OpenAI client that aicoder uses."""

    def __init__(self, scripted_responses: Optional[List[List[Any]]] = None, models: Optional[List[str]] = None):
        self.chat = SimpleNamespace(completions=FakeCompletions(scripted_responses or []))
        self._models = models or ["test-model", "another-model"]

    class _ModelsAPI:
        def __init__(self, ids):
            self._ids = ids

        def list(self):
            return SimpleNamespace(data=[SimpleNamespace(id=i) for i in self._ids])

    @property
    def models(self):
        return FakeClient._ModelsAPI(self._models)
