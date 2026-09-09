"""Tools the agent can call to inspect and change a codebase.

Each tool is described to the model with an OpenAI function schema (LiteLLM is
OpenAI-compatible) and backed by a plain Python handler. Handlers take the parsed
argument dict and the run ``Config``, return a string (the tool result), and
raise ``ToolError`` for expected, user-facing failures.

Tools flagged ``mutating`` change the filesystem, run commands, commit code, or
create GitLab issues; the CLI gates those behind a confirmation prompt unless
auto-approve is on.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from aicoder import gitlab, gitops
from aicoder.config import Config

# Cap how much file/command output we feed back to the model in one result, so a
# single huge file can't blow up the context window.
MAX_OUTPUT_CHARS = 30_000


class ToolError(Exception):
    """An expected failure whose message is safe to return to the model."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any], Config], str]
    mutating: bool = False

    def schema(self) -> Dict[str, Any]:
        """The OpenAI ``tools=[...]`` entry for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    omitted = len(text) - MAX_OUTPUT_CHARS
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated {omitted} characters]"


def _resolve(config: Config, path: str) -> str:
    """Resolve ``path`` against the working directory."""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(config.workdir, path))


# --- Filesystem handlers ----------------------------------------------------


def _read_file(args: Dict[str, Any], config: Config) -> str:
    path = _resolve(config, args["path"])
    if not os.path.isfile(path):
        raise ToolError(f"No such file: {args['path']}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as exc:
        raise ToolError(f"Cannot read {args['path']} as UTF-8 text: {exc}")
    return content if content else "(file is empty)"


def _write_file(args: Dict[str, Any], config: Config) -> str:
    path = _resolve(config, args["path"])
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


def _str_replace(args: Dict[str, Any], config: Config) -> str:
    path = _resolve(config, args["path"])
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


def _list_directory(args: Dict[str, Any], config: Config) -> str:
    path = _resolve(config, args.get("path", "."))
    if not os.path.isdir(path):
        raise ToolError(f"No such directory: {args.get('path', '.')}")
    entries = sorted(os.listdir(path))
    if not entries:
        return "(empty directory)"
    lines = [f"{n}/" if os.path.isdir(os.path.join(path, n)) else n for n in entries]
    return _truncate("\n".join(lines))


def _search(args: Dict[str, Any], config: Config) -> str:
    pattern = args["pattern"]
    root = _resolve(config, args.get("path", "."))
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
                            rel = os.path.relpath(full, config.workdir)
                            matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(matches) >= 200:
                                matches.append("... [more matches omitted]")
                                return "\n".join(matches)
            except (UnicodeDecodeError, OSError):
                continue  # skip binaries and unreadable files
    if not matches:
        return f"No matches for {pattern!r}."
    return _truncate("\n".join(matches))


def _run_command(args: Dict[str, Any], config: Config) -> str:
    command = args["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=config.workdir,
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


# --- Git handlers -----------------------------------------------------------


def _git_status(args: Dict[str, Any], config: Config) -> str:
    try:
        return gitops.status(config)
    except gitops.GitError as exc:
        raise ToolError(str(exc))


def _git_diff(args: Dict[str, Any], config: Config) -> str:
    try:
        return gitops.diff(config, staged=bool(args.get("staged", False)), path=args.get("path"))
    except gitops.GitError as exc:
        raise ToolError(str(exc))


def _git_log(args: Dict[str, Any], config: Config) -> str:
    try:
        return gitops.log(config, count=int(args.get("count", 10)))
    except gitops.GitError as exc:
        raise ToolError(str(exc))


def _git_add(args: Dict[str, Any], config: Config) -> str:
    paths = args.get("paths")
    if isinstance(paths, str):
        paths = [paths]
    try:
        return gitops.add(config, paths or [])
    except gitops.GitError as exc:
        raise ToolError(str(exc))


def _git_commit(args: Dict[str, Any], config: Config) -> str:
    try:
        return gitops.commit(config, args["message"], add_all=bool(args.get("all", False)))
    except gitops.GitError as exc:
        raise ToolError(str(exc))


# --- GitLab handlers --------------------------------------------------------


def _gitlab_list_issues(args: Dict[str, Any], config: Config) -> str:
    try:
        issues = gitlab.list_issues(
            config,
            project=args.get("project"),
            state=args.get("state", "opened"),
            search=args.get("search"),
            limit=int(args.get("limit", 20)),
        )
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    if not issues:
        return "(no matching issues)"
    return "\n".join(gitlab.format_issue_short(i) for i in issues)


def _gitlab_get_issue(args: Dict[str, Any], config: Config) -> str:
    try:
        issue = gitlab.get_issue(config, int(args["issue_iid"]), project=args.get("project"))
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    return gitlab.format_issue_detail(issue)


def _gitlab_create_issue(args: Dict[str, Any], config: Config) -> str:
    labels = args.get("labels")
    if isinstance(labels, str):
        labels = [s.strip() for s in labels.split(",") if s.strip()]
    try:
        issue = gitlab.create_issue(
            config,
            title=args["title"],
            description=args.get("description", ""),
            project=args.get("project"),
            labels=labels,
        )
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    return f"Created issue #{issue.get('iid')}: {issue.get('web_url', '')}"


def _gitlab_list_mrs(args: Dict[str, Any], config: Config) -> str:
    try:
        mrs = gitlab.list_merge_requests(
            config,
            project=args.get("project"),
            state=args.get("state", "opened"),
            search=args.get("search"),
            limit=int(args.get("limit", 20)),
        )
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    if not mrs:
        return "(no matching merge requests)"
    return "\n".join(gitlab.format_mr_short(m) for m in mrs)


def _gitlab_get_mr(args: Dict[str, Any], config: Config) -> str:
    try:
        mr = gitlab.get_merge_request(config, int(args["mr_iid"]), project=args.get("project"))
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    return gitlab.format_mr_detail(mr)


def _gitlab_create_mr(args: Dict[str, Any], config: Config) -> str:
    labels = args.get("labels")
    if isinstance(labels, str):
        labels = [s.strip() for s in labels.split(",") if s.strip()]
    try:
        mr = gitlab.create_merge_request(
            config,
            source_branch=args["source_branch"],
            target_branch=args["target_branch"],
            title=args["title"],
            description=args.get("description", ""),
            project=args.get("project"),
            remove_source_branch=bool(args.get("remove_source_branch", False)),
            labels=labels,
        )
    except gitlab.GitLabError as exc:
        raise ToolError(str(exc))
    return f"Created merge request !{mr.get('iid')}: {mr.get('web_url', '')}"


# --- Registry ---------------------------------------------------------------

_PROJECT_PARAM = {
    "type": "string",
    "description": (
        "GitLab project id or 'group/path'. Optional — if omitted it falls back to "
        "$GITLAB_PROJECT, then to the git 'origin' remote of the working directory. "
        "Only ask the user for it if none of those resolve."
    ),
}

TOOLS: List[Tool] = [
    Tool(
        name="read_file",
        description="Read the full contents of a text file, relative to the working directory.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the file."}},
            "required": ["path"],
        },
        handler=_read_file,
    ),
    Tool(
        name="list_directory",
        description="List the entries of a directory. Directories are suffixed with '/'.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path. Defaults to '.'."}},
        },
        handler=_list_directory,
    ),
    Tool(
        name="search",
        description=(
            "Recursively search text files under a directory for a literal substring. "
            "Returns matching 'path:line: text' entries."
        ),
        parameters={
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
        parameters={
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
        parameters={
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
            "and stderr. Use for builds, tests, and linters."
        ),
        parameters={
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
    # --- git ---
    Tool(
        name="git_status",
        description="Show the working tree status (branch and changed files).",
        parameters={"type": "object", "properties": {}},
        handler=_git_status,
    ),
    Tool(
        name="git_diff",
        description="Show the git diff. Set staged=true for the staged diff; optionally limit to a path.",
        parameters={
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "description": "Show the staged diff instead of unstaged."},
                "path": {"type": "string", "description": "Limit the diff to this path."},
            },
        },
        handler=_git_diff,
    ),
    Tool(
        name="git_log",
        description="Show recent commits (one line each).",
        parameters={
            "type": "object",
            "properties": {"count": {"type": "integer", "description": "How many commits (default 10)."}},
        },
        handler=_git_log,
    ),
    Tool(
        name="git_add",
        description="Stage files for commit.",
        parameters={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to stage (use ['.'] for everything).",
                }
            },
            "required": ["paths"],
        },
        handler=_git_add,
        mutating=True,
    ),
    Tool(
        name="git_commit",
        description="Create a git commit with a message. Set all=true to stage tracked changes first.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The commit message."},
                "all": {"type": "boolean", "description": "Stage all tracked changes first (git commit -a)."},
            },
            "required": ["message"],
        },
        handler=_git_commit,
        mutating=True,
    ),
    # --- GitLab ---
    Tool(
        name="gitlab_list_issues",
        description="List issues (tickets) in a GitLab project.",
        parameters={
            "type": "object",
            "properties": {
                "project": _PROJECT_PARAM,
                "state": {"type": "string", "enum": ["opened", "closed", "all"], "description": "Default opened."},
                "search": {"type": "string", "description": "Filter issues by text."},
                "limit": {"type": "integer", "description": "Max issues to return (default 20)."},
            },
        },
        handler=_gitlab_list_issues,
    ),
    Tool(
        name="gitlab_get_issue",
        description="Get the details of one GitLab issue by its project-scoped iid.",
        parameters={
            "type": "object",
            "properties": {
                "issue_iid": {"type": "integer", "description": "The issue's project-scoped id (iid)."},
                "project": _PROJECT_PARAM,
            },
            "required": ["issue_iid"],
        },
        handler=_gitlab_get_issue,
    ),
    Tool(
        name="gitlab_create_issue",
        description="Create a new issue (ticket) in a GitLab project.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Issue title."},
                "description": {"type": "string", "description": "Issue description (Markdown)."},
                "project": _PROJECT_PARAM,
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels to apply.",
                },
            },
            "required": ["title"],
        },
        handler=_gitlab_create_issue,
        mutating=True,
    ),
    Tool(
        name="gitlab_list_merge_requests",
        description="List merge requests in a GitLab project.",
        parameters={
            "type": "object",
            "properties": {
                "project": _PROJECT_PARAM,
                "state": {
                    "type": "string",
                    "enum": ["opened", "closed", "merged", "all"],
                    "description": "Default opened.",
                },
                "search": {"type": "string", "description": "Filter by text."},
                "limit": {"type": "integer", "description": "Max to return (default 20)."},
            },
        },
        handler=_gitlab_list_mrs,
    ),
    Tool(
        name="gitlab_get_merge_request",
        description="Get the details of one GitLab merge request by its project-scoped iid.",
        parameters={
            "type": "object",
            "properties": {
                "mr_iid": {"type": "integer", "description": "The merge request's iid."},
                "project": _PROJECT_PARAM,
            },
            "required": ["mr_iid"],
        },
        handler=_gitlab_get_mr,
    ),
    Tool(
        name="gitlab_create_merge_request",
        description=(
            "Open a new merge request from a source branch into a target branch "
            "in a GitLab project."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source_branch": {"type": "string", "description": "Branch with the changes."},
                "target_branch": {"type": "string", "description": "Branch to merge into (e.g. main)."},
                "title": {"type": "string", "description": "Merge request title."},
                "description": {"type": "string", "description": "Description (Markdown)."},
                "project": _PROJECT_PARAM,
                "remove_source_branch": {
                    "type": "boolean",
                    "description": "Delete the source branch after merge.",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels.",
                },
            },
            "required": ["source_branch", "target_branch", "title"],
        },
        handler=_gitlab_create_mr,
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
    if name == "git_commit":
        return f"git commit -m {args.get('message', '')!r}"
    if name == "git_add":
        return f"git add {' '.join(args.get('paths', []) or [])}"
    if name in ("git_status", "git_diff", "git_log"):
        return name.replace("_", " ")
    if name == "gitlab_create_issue":
        return f"gitlab: create issue {args.get('title', '')!r}"
    if name == "gitlab_list_issues":
        return "gitlab: list issues"
    if name == "gitlab_get_issue":
        return f"gitlab: get issue #{args.get('issue_iid', '?')}"
    if name == "gitlab_create_merge_request":
        return f"gitlab: create MR {args.get('source_branch', '?')}→{args.get('target_branch', '?')}"
    if name == "gitlab_list_merge_requests":
        return "gitlab: list merge requests"
    if name == "gitlab_get_merge_request":
        return f"gitlab: get MR !{args.get('mr_iid', '?')}"
    if name in ("read_file", "write_file", "str_replace"):
        return f"{name} {args.get('path', '')}"
    if name == "list_directory":
        return f"list_directory {args.get('path', '.')}"
    if name == "search":
        return f"search {args.get('pattern', '')!r} in {args.get('path', '.')}"
    return name
