import pytest

from aicoder import tools
from aicoder.tools import ToolError, get_tool, tool_schemas


def call(name, args, config):
    return get_tool(name).handler(args, config)


def test_write_read_roundtrip(config):
    out = call("write_file", {"path": "a.py", "content": "x = 1\n"}, config)
    assert "Created a.py" in out
    assert call("read_file", {"path": "a.py"}, config) == "x = 1\n"


def test_write_overwrite_and_nested_dir(config):
    call("write_file", {"path": "pkg/mod.py", "content": "a"}, config)
    out = call("write_file", {"path": "pkg/mod.py", "content": "b"}, config)
    assert "Overwrote" in out
    assert call("read_file", {"path": "pkg/mod.py"}, config) == "b"


def test_read_missing_file(config):
    with pytest.raises(ToolError):
        call("read_file", {"path": "nope.txt"}, config)


def test_read_empty_file(config):
    call("write_file", {"path": "empty.txt", "content": ""}, config)
    assert call("read_file", {"path": "empty.txt"}, config) == "(file is empty)"


def test_str_replace_unique(config):
    call("write_file", {"path": "a.py", "content": "x = 1\ny = 2\n"}, config)
    call("str_replace", {"path": "a.py", "old_str": "x = 1", "new_str": "x = 42"}, config)
    assert call("read_file", {"path": "a.py"}, config) == "x = 42\ny = 2\n"


def test_str_replace_not_found(config):
    call("write_file", {"path": "a.py", "content": "x = 1\n"}, config)
    with pytest.raises(ToolError, match="not found"):
        call("str_replace", {"path": "a.py", "old_str": "zzz", "new_str": "q"}, config)


def test_str_replace_ambiguous(config):
    call("write_file", {"path": "a.py", "content": "a\na\n"}, config)
    with pytest.raises(ToolError, match="unique"):
        call("str_replace", {"path": "a.py", "old_str": "a", "new_str": "b"}, config)


def test_list_directory(config):
    call("write_file", {"path": "a.txt", "content": "1"}, config)
    call("write_file", {"path": "sub/b.txt", "content": "2"}, config)
    out = call("list_directory", {}, config)
    assert "a.txt" in out
    assert "sub/" in out


def test_search_finds_matches(config):
    call("write_file", {"path": "a.py", "content": "needle here\nother\n"}, config)
    out = call("search", {"pattern": "needle"}, config)
    assert "a.py:1:" in out


def test_search_no_matches(config):
    call("write_file", {"path": "a.py", "content": "nothing\n"}, config)
    assert "No matches" in call("search", {"pattern": "zzz"}, config)


def test_search_skips_git_dir(config):
    import os
    os.makedirs(os.path.join(config.workdir, ".git"))
    with open(os.path.join(config.workdir, ".git", "x.txt"), "w") as f:
        f.write("needle\n")
    assert "No matches" in call("search", {"pattern": "needle"}, config)


def test_run_command(config):
    out = call("run_command", {"command": "echo hello"}, config)
    assert "exit code: 0" in out
    assert "hello" in out


def test_run_command_nonzero(config):
    out = call("run_command", {"command": "exit 3"}, config)
    assert "exit code: 3" in out


def test_truncation():
    long = "y" * (tools.MAX_OUTPUT_CHARS + 100)
    assert "truncated" in tools._truncate(long)
    assert tools._truncate("short") == "short"


def test_all_schemas_are_openai_function_shape():
    schemas = tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert {
        "read_file", "write_file", "git_commit",
        "gitlab_create_issue", "gitlab_create_merge_request",
    } <= names
    for s in schemas:
        assert s["type"] == "function"
        assert "parameters" in s["function"]


def test_mutating_flags():
    assert get_tool("write_file").mutating
    assert get_tool("git_commit").mutating
    assert get_tool("gitlab_create_issue").mutating
    assert not get_tool("read_file").mutating
    assert not get_tool("git_status").mutating
    assert not get_tool("gitlab_list_issues").mutating
