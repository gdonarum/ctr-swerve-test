"""Command-line entrypoint: argument parsing, the REPL, slash commands, and
one-shot mode."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

from aicoder import __version__, certs, gitlab, gitops, llm, session, ui
from aicoder.agent import Agent, AgentError
from aicoder.config import Config, load_dotenv

HELP_TEXT = """\
Commands:
  /help                 show this help
  /models               list models available on the LiteLLM proxy
  /model [name]         show or set the active model
  /commit <message>     commit tracked changes with a message
  /issues [project]     list open GitLab issues
  /issue <iid> [proj]   show one GitLab issue
  /mrs [project]        list open GitLab merge requests
  /mr <iid> [project]   show one GitLab merge request
  /save [name]          save the current conversation
  /resume <name>        resume a saved conversation
  /sessions             list saved conversations
  /reset                clear the conversation history
  /exit, /quit          leave

Anything else is sent to the assistant. It can also edit files, run commands,
use git, and manage GitLab issues and merge requests (with your confirmation).
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcs",
        description="DCS Code CLI — a terminal AI coding assistant powered by a LiteLLM proxy.",
    )
    parser.add_argument("prompt", nargs="*", help="A one-shot request. Omit for an interactive session.")
    parser.add_argument("--model", help="Model id to use (default: $LITELLM_MODEL, or first available).")
    parser.add_argument("--max-tokens", type=int, help="Max output tokens per response.")
    parser.add_argument("--workdir", help="Directory to operate in (default: current directory).")
    parser.add_argument(
        "-c", "--continue", dest="continue_", action="store_true",
        help="Resume this directory's autosaved session on startup.",
    )
    parser.add_argument(
        "--no-autosave", action="store_true",
        help="Do not autosave the conversation for this directory.",
    )
    parser.add_argument("--base-url", help="LiteLLM base URL (default: $LITELLM_BASE_URL).")
    parser.add_argument(
        "--env-file", default=".env",
        help="Path to a .env file to load (default: .env in the current directory).",
    )
    parser.add_argument(
        "--ca-bundle",
        help="Path to a CA bundle/cert (e.g. your Zscaler root) for TLS verification.",
    )
    parser.add_argument(
        "--system-certs",
        action="store_true",
        help="Trust the OS certificate store (needs 'truststore'; good for Zscaler).",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Auto-approve file writes, commands, commits, and issue/MR creation.",
    )
    parser.add_argument("--version", action="version", version=f"DCS Code CLI {__version__}")
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
        if tool.name == "gitlab_create_merge_request":
            body = (
                f"{args.get('source_branch', '')} → {args.get('target_branch', '')}\n"
                f"title: {args.get('title', '')}\n\n{args.get('description', '')}"
            )
            ui.diff_preview("gitlab: create merge request", body, "markdown")
            return ui.confirm("Create this merge request?")
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


def _cmd_mrs(agent: Agent, arg: str) -> None:
    project = arg.strip() or None
    try:
        mrs = gitlab.list_merge_requests(agent.config, project=project)
    except gitlab.GitLabError as exc:
        ui.error(str(exc))
        return
    if not mrs:
        ui.info("(no open merge requests)")
        return
    for mr in mrs:
        ui.info(gitlab.format_mr_short(mr))


def _cmd_mr(agent: Agent, arg: str) -> None:
    parts = arg.split()
    if not parts:
        ui.error("Usage: /mr <iid> [project]")
        return
    try:
        iid = int(parts[0])
    except ValueError:
        ui.error("The merge request id must be a number.")
        return
    project = parts[1] if len(parts) > 1 else None
    try:
        mr = gitlab.get_merge_request(agent.config, iid, project=project)
    except gitlab.GitLabError as exc:
        ui.error(str(exc))
        return
    ui.info(gitlab.format_mr_detail(mr))


def _cmd_save(agent: Agent, arg: str) -> None:
    try:
        name = session.save(
            agent.messages, agent.config.model, agent.config.workdir, arg.strip() or None
        )
    except session.SessionError as exc:
        ui.error(str(exc))
        return
    ui.info(f"saved session {name!r}")


def _apply_session(agent: Agent, data: dict, label: str) -> None:
    agent.messages = data["messages"]
    if data.get("model"):
        agent.config.model = data["model"]
    ui.info(f"resumed {label} ({len(agent.messages)} messages, model {agent.config.model})")


def _cmd_resume(agent: Agent, arg: str) -> None:
    name = arg.strip()
    try:
        if not name:
            # no name: resume this directory's autosave
            data = session.load_autosave(agent.config.workdir)
            label = "autosaved session"
        else:
            data = session.load(name)
            label = f"session {name!r}"
    except session.SessionError as exc:
        ui.error(str(exc))
        return
    _apply_session(agent, data, label)


def _autosave(agent: Agent) -> None:
    if agent.config.autosave and len(agent.messages) > 1:
        session.autosave(agent.messages, agent.config.model, agent.config.workdir)


def _cmd_sessions(agent: Agent) -> None:
    names = session.list_sessions()
    if not names:
        ui.info("(no saved sessions)")
        return
    for name in names:
        ui.info(name)


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
    elif command == "/mrs":
        _cmd_mrs(agent, arg)
    elif command == "/mr":
        _cmd_mr(agent, arg)
    elif command == "/save":
        _cmd_save(agent, arg)
    elif command == "/resume":
        _cmd_resume(agent, arg)
    elif command == "/sessions":
        _cmd_sessions(agent)
    else:
        ui.error(f"Unknown command {command!r}. Try /help.")
    return True


# --- run loops --------------------------------------------------------------


def _repl(agent: Agent) -> int:
    hint = ""
    if agent.config.autosave and session.has_autosave(agent.config.workdir):
        hint = "An autosaved session exists here — /resume (or -c at startup) to continue."
    ui.banner(agent.config.model or "(unset)", os.path.abspath(agent.config.workdir), hint)
    _resolve_model(agent)
    while True:
        try:
            message = ui.user_prompt().strip()
        except (EOFError, KeyboardInterrupt):
            ui.newline()
            _autosave(agent)
            ui.info("bye")
            return 0

        if not message:
            continue
        if message.startswith("/"):
            keep_going = _handle_slash(agent, message)
            _autosave(agent)
            if not keep_going:
                return 0
            continue

        try:
            agent.send(message)
        except AgentError as exc:
            ui.error(str(exc))
        except KeyboardInterrupt:
            ui.newline()
            ui.info("[interrupted]")
        finally:
            _autosave(agent)


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
    finally:
        _autosave(agent)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    # Load a .env file if present, so copying .env.example to .env is enough —
    # no need to `export` or `source` it. Real environment variables still win.
    loaded = load_dotenv(args.env_file)
    if not loaded and args.env_file != ".env":
        ui.error(f"env file not found: {args.env_file}")
        return 2

    config = Config.from_env(
        model=args.model,
        max_tokens=args.max_tokens,
        workdir=args.workdir,
        base_url=args.base_url,
        auto_approve=args.yes,
        ca_bundle=args.ca_bundle,
        use_system_certs=True if args.system_certs else None,
        autosave=False if args.no_autosave else None,
    )

    # Apply corporate TLS trust (e.g. Zscaler) up front so both the LLM and
    # GitLab clients pick it up. A CA bundle is picked up per-request/client.
    try:
        certs.apply_system_certs(config)
    except certs.CertError as exc:
        ui.error(str(exc))
        return 2

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

    if args.continue_:
        try:
            _apply_session(agent, session.load_autosave(config.workdir), "autosaved session")
        except session.SessionError as exc:
            ui.error(str(exc))

    if args.prompt:
        return _one_shot(agent, " ".join(args.prompt))
    return _repl(agent)


if __name__ == "__main__":
    sys.exit(main())
