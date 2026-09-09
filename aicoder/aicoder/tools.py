"""Tools the agent can call to inspect and change a codebase.

Each tool is described to the model by an Anthropic tool schema and backed by a
plain Python handler. Handlers return a string (the ``tool_result`` content) and
raise ``ToolError`` for expected, user-facing failures.

Tools flagged ``mutating`` change the filesystem or run commands; the CLI gates
those behind a confirmation prompt unless auto-approve is on.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# Cap how much file/command output we feed back to the model in one result, so a
# single huge file can't blow up the context window.
MAX_OUTPUT_CHARS = 30_000


class ToolError(Exception):
    """An expected failure whose message is safe to return to the model."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any], str], str]
    mutating: bool = False

    def schema(self) -> Dict[str, Any]:
        """The dict form the Messages API expects in ``tools=[...]``."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    omitted = len(text) - MAX_OUTPUT_CHARS
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated {omitted} characters]"


def _resolve(workdir: str, path: str) -> str:
    """Resolve ``path`` against the working directory."""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(workdir, path))


# --- Handlers ---------------------------------------------------------------


def _read_file(args: Dict[str, Any], workdir: str) -> str:
    path = _resolve(workdir, args["path"])
    if not os.path.isfile(path):
        raise ToolError(f"No such file: {args['path']}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as exc:
        raise ToolError(f"Cannot read {args['path']} as UTF-8 text: {exc}")
    if content == "":
        return "(file is empty)"
    return _truncate(content)


def _write_file(args: Dict[str, Any], workdir: str) -> str:
    path = _resolve(workdir, args["path"])
    content = args["content"]
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    existed = os.path.isfile(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    verb = "Overwrote" if existed else "Created"
    lines = content.count("\n") + 1 if content else 0
    return f"{verb} {args['path']} ({lines} lines, {len(content)} bytes)."


def _str_replace(args: Dict[str, Any], workdir: str) -> str:
    path = _resolve(workdir, args["path"])
    if not os.path.isfile(path):
        raise ToolError(f"No such file: {args['path']}")
    old = args["old_str"]
    new = args["new_str"]
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        raise ToolError(
            "old_str was not found in the file. It must match exactly, "
            "including whitespace and indentation."
        )
    if count > 1:
        raise ToolError(
            f"old_str matched {count} times; it must be unique. Add surrounding "
            "context to the snippet so it matches exactly once."
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.replace(old, new, 1))
    return f"Edited {args['path']} (1 replacement)."


def _list_directory(args: Dict[str, Any], workdir: str) -> str:
    path = _resolve(workdir, args.get("path", "."))
    if not os.path.isdir(path):
        raise ToolError(f"No such directory: {args.get('path', '.')}")
    entries = sorted(os.listdir(path))
    if not entries:
        return "(empty directory)"
    lines: List[str] = []
    for name in entries:
        full = os.path.join(path, name)
        lines.append(f"{name}/" if os.path.isdir(full) else name)
    return _truncate("\n".join(lines))


def _search(args: Dict[str, Any], workdir: str) -> str:
    pattern = args["pattern"]
    root = _resolve(workdir, args.get("path", "."))
    matches: List[str] = []
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "build", "dist"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            try:
                with open(full, "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, start=1):
                        if pattern in line:
                            rel = os.path.relpath(full, workdir)
                            matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(matches) >= 200:
                                matches.append("... [more matches omitted]")
                                return "\n".join(matches)
            except (UnicodeDecodeError, OSError):
                continue  # skip binaries and unreadable files
    if not matches:
        return f"No matches for {pattern!r}."
    return _truncate("\n".join(matches))


def _run_command(args: Dict[str, Any], workdir: str) -> str:
    command = args["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=args.get("timeout", 120),
        )
    except subprocess.TimeoutExpired:
        raise ToolError("Command timed out.")
    parts = [f"exit code: {result.returncode}"]
    if result.stdout:
        parts.append("stdout:\n" + result.stdout)
    if result.stderr:
        parts.append("stderr:\n" + result.stderr)
    return _truncate("\n".join(parts))


# --- Registry ---------------------------------------------------------------

TOOLS: List[Tool] = [
    Tool(
        name="read_file",
        description="Read the full contents of a text file, relative to the working directory.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file."}},
            "required": ["path"],
        },
        handler=_read_file,
    ),
    Tool(
        name="list_directory",
        description="List the entries of a directory. Directories are suffixed with '/'.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path. Defaults to '.'."}
            },
        },
        handler=_list_directory,
    ),
    Tool(
        name="search",
        description=(
            "Recursively search text files under a directory for a literal substring. "
            "Returns matching 'path:line: text' entries."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Literal substring to search for."},
                "path": {"type": "string", "description": "Root directory. Defaults to '.'."},
            },
            "required": ["pattern"],
        },
        handler=_search,
    ),
    Tool(
        name="write_file",
        description=(
            "Create a new file or completely overwrite an existing one. Prefer str_replace "
            "for small edits to existing files."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."},
                "content": {"type": "string", "description": "The full file contents."},
            },
            "required": ["path", "content"],
        },
        handler=_write_file,
        mutating=True,
    ),
    Tool(
        name="str_replace",
        description=(
            "Replace an exact, unique snippet in an existing file. old_str must match the "
            "file exactly (including whitespace) and appear exactly once."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."},
                "old_str": {"type": "string", "description": "Exact text to replace."},
                "new_str": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_str", "new_str"],
        },
        handler=_str_replace,
        mutating=True,
    ),
    Tool(
        name="run_command",
        description=(
            "Run a shell command in the working directory and return its exit code, stdout, "
            "and stderr. Use for builds, tests, linters, and git."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)."},
            },
            "required": ["command"],
        },
        handler=_run_command,
        mutating=True,
    ),
]

_BY_NAME: Dict[str, Tool] = {t.name: t for t in TOOLS}


def get_tool(name: str) -> Optional[Tool]:
    return _BY_NAME.get(name)


def tool_schemas() -> List[Dict[str, Any]]:
    return [t.schema() for t in TOOLS]


def describe_call(name: str, args: Dict[str, Any]) -> str:
    """A short one-line summary of a pending tool call, for the UI."""
    if name == "run_command":
        return f"$ {args.get('command', '')}"
    if name in ("read_file", "write_file", "str_replace"):
        return f"{name} {args.get('path', '')}"
    if name == "list_directory":
        return f"list_directory {args.get('path', '.')}"
    if name == "search":
        return f"search {args.get('pattern', '')!r} in {args.get('path', '.')}"
    return name
