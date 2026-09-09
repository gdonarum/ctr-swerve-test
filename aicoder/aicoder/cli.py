"""Command-line entrypoint: argument parsing, the REPL, slash commands, and
one-shot mode."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

from aicoder import __version__, gitlab, gitops, llm, ui
from aicoder.agent import Agent, AgentError
from aicoder.config import Config

HELP_TEXT = """\
Commands:
  /help                 show this help
  /models               list models available on the LiteLLM proxy
  /model [name]         show or set the active model
  /commit <message>     commit tracked changes with a message
  /issues [project]     list open GitLab issues
  /issue <iid> [proj]   show one GitLab issue
  /reset                clear the conversation history
  /exit, /quit          leave

Anything else is sent to the assistant. It can also edit files, run commands,
use git, and create GitLab issues on your behalf (with your confirmation).
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicoder",
        description="A terminal AI coding assistant powered by a LiteLLM proxy.",
    )
    parser.add_argument("prompt", nargs="*", help="A one-shot request. Omit for an interactive session.")
    parser.add_argument("--model", help="Model id to use (default: $LITELLM_MODEL, or first available).")
    parser.add_argument("--max-tokens", type=int, help="Max output tokens per response.")
    parser.add_argument("--workdir", help="Directory to operate in (default: current directory).")
    parser.add_argument("--base-url", help="LiteLLM base URL (default: $LITELLM_BASE_URL).")
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Auto-approve file writes, commands, commits, and issue creation.",
    )
    parser.add_argument("--version", action="version", version=f"aicoder {__version__}")
    return parser


# --- approval preview -------------------------------------------------------


def _make_approver(config: Config):
    def approver(tool, args: Dict[str, Any]) -> bool:
        if tool.name == "write_file":
            content = args.get("content", "")
            preview = content if len(content) <= 2000 else content[:2000] + "\n… [truncated]"
            ui.diff_preview(f"write_file → {args.get('path', '')}", preview, _language_for(args.get("path", "")))
            return ui.confirm("Write this file?")
        if tool.name == "str_replace":
            body = f"- {args.get('old_str', '')}\n+ {args.get('new_str', '')}"
            ui.diff_preview(f"str_replace → {args.get('path', '')}", body)
            return ui.confirm("Apply this edit?")
        if tool.name == "run_command":
            ui.diff_preview("run_command", f"$ {args.get('command', '')}", "bash")
            return ui.confirm("Run this command?")
        if tool.name == "git_commit":
            ui.diff_preview("git commit", args.get("message", ""), "text")
            return ui.confirm("Create this commit?")
        if tool.name == "git_add":
            ui.diff_preview("git add", " ".join(args.get("paths", []) or []), "text")
            return ui.confirm("Stage these paths?")
        if tool.name == "gitlab_create_issue":
            body = f"title: {args.get('title', '')}\n\n{args.get('description', '')}"
            ui.diff_preview("gitlab: create issue", body, "markdown")
            return ui.confirm("Create this issue?")
        return ui.confirm(f"Run {tool.name}?")

    return approver


def _language_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java",
        ".json": "json", ".md": "markdown", ".sh": "bash", ".html": "html",
        ".css": "css", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
    }.get(ext, "text")


# --- slash commands ---------------------------------------------------------


def _resolve_model(agent: Agent, quiet: bool = False) -> None:
    """If no model is set, pick the first one the proxy offers."""
    if agent.config.model:
        return
    try:
        models = llm.list_models(agent.client)
    except llm.LLMError as exc:
        if not quiet:
            ui.error(str(exc))
        return
    if models:
        agent.config.model = models[0]
        if not quiet:
            ui.info(f"No model set; using {models[0]}. Use /model to change it.")


def _cmd_models(agent: Agent) -> None:
    try:
        models = llm.list_models(agent.client)
    except llm.LLMError as exc:
        ui.error(str(exc))
        return
    if not models:
        ui.info("(no models reported by the proxy)")
        return
    for m in models:
        marker = "* " if m == agent.config.model else "  "
        ui.info(f"{marker}{m}")


def _cmd_model(agent: Agent, arg: str) -> None:
    name = arg.strip()
    if not name:
        ui.info(f"active model: {agent.config.model or '(none)'}")
        return
    try:
        models = llm.list_models(agent.client)
    except llm.LLMError:
        models = []
    if models and name not in models:
        ui.error(f"Unknown model {name!r}. Use /models to see the list.")
        return
    agent.config.model = name
    ui.info(f"active model: {name}")


def _cmd_commit(agent: Agent, message: str) -> None:
    message = message.strip()
    if not message:
        ui.error("Usage: /commit <message>")
        return
    if not agent.config.auto_approve:
        ui.diff_preview("git commit (all tracked changes)", message, "text")
        if not ui.confirm("Create this commit?"):
            ui.info("aborted")
            return
    try:
        ui.info(gitops.commit(agent.config, message, add_all=True))
    except gitops.GitError as exc:
        ui.error(str(exc))


def _cmd_issues(agent: Agent, arg: str) -> None:
    project = arg.strip() or None
    try:
        issues = gitlab.list_issues(agent.config, project=project)
    except gitlab.GitLabError as exc:
        ui.error(str(exc))
        return
    if not issues:
        ui.info("(no open issues)")
        return
    for issue in issues:
        ui.info(gitlab.format_issue_short(issue))


def _cmd_issue(agent: Agent, arg: str) -> None:
    parts = arg.split()
    if not parts:
        ui.error("Usage: /issue <iid> [project]")
        return
    try:
        iid = int(parts[0])
    except ValueError:
        ui.error("The issue id must be a number.")
        return
    project = parts[1] if len(parts) > 1 else None
    try:
        issue = gitlab.get_issue(agent.config, iid, project=project)
    except gitlab.GitLabError as exc:
        ui.error(str(exc))
        return
    ui.info(gitlab.format_issue_detail(issue))


def _handle_slash(agent: Agent, message: str) -> bool:
    """Handle a /command. Returns True if the REPL should keep running,
    False if it should exit."""
    command, _, arg = message.partition(" ")
    if command in ("/exit", "/quit"):
        ui.info("bye")
        return False
    if command == "/help":
        ui.info(HELP_TEXT)
    elif command == "/reset":
        agent.reset()
        ui.info("conversation cleared")
    elif command == "/models":
        _cmd_models(agent)
    elif command == "/model":
        _cmd_model(agent, arg)
    elif command == "/commit":
        _cmd_commit(agent, arg)
    elif command == "/issues":
        _cmd_issues(agent, arg)
    elif command == "/issue":
        _cmd_issue(agent, arg)
    else:
        ui.error(f"Unknown command {command!r}. Try /help.")
    return True


# --- run loops --------------------------------------------------------------


def _repl(agent: Agent) -> int:
    ui.banner(agent.config.model or "(unset)", os.path.abspath(agent.config.workdir))
    _resolve_model(agent)
    while True:
        try:
            message = ui.user_prompt().strip()
        except (EOFError, KeyboardInterrupt):
            ui.newline()
            ui.info("bye")
            return 0

        if not message:
            continue
        if message.startswith("/"):
            if not _handle_slash(agent, message):
                return 0
            continue

        try:
            agent.send(message)
        except AgentError as exc:
            ui.error(str(exc))
        except KeyboardInterrupt:
            ui.newline()
            ui.info("[interrupted]")


def _one_shot(agent: Agent, prompt: str) -> int:
    _resolve_model(agent, quiet=True)
    try:
        agent.send(prompt)
        return 0
    except AgentError as exc:
        ui.error(str(exc))
        return 1
    except KeyboardInterrupt:
        ui.newline()
        return 130


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    config = Config.from_env(
        model=args.model,
        max_tokens=args.max_tokens,
        workdir=args.workdir,
        base_url=args.base_url,
        auto_approve=args.yes,
    )

    if not config.has_llm_credentials():
        ui.error(
            "LiteLLM is not configured. Set LITELLM_BASE_URL and LITELLM_API_KEY "
            "(see .env.example) and try again."
        )
        return 2

    if not os.path.isdir(config.workdir):
        ui.error(f"Working directory does not exist: {config.workdir}")
        return 2

    try:
        agent = Agent(config, _make_approver(config))
    except llm.LLMError as exc:
        ui.error(str(exc))
        return 2
    except Exception as exc:  # defensive
        ui.error(f"Failed to initialize: {exc}")
        return 2

    if args.prompt:
        return _one_shot(agent, " ".join(args.prompt))
    return _repl(agent)


if __name__ == "__main__":
    sys.exit(main())
