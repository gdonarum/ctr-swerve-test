"""Command-line entrypoint: argument parsing, the REPL, and single-shot mode."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict

from aicoder import __version__, ui
from aicoder.agent import Agent, AgentError
from aicoder.config import Config, has_api_key


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicoder",
        description="A small AI coding assistant for your terminal, powered by Claude.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="A one-shot request. Omit to start an interactive session.",
    )
    parser.add_argument("--model", help="Model id to use (default: claude-opus-5 or $AICODER_MODEL).")
    parser.add_argument("--max-tokens", type=int, help="Max output tokens per response.")
    parser.add_argument("--workdir", help="Directory to operate in (default: current directory).")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-approve file writes and shell commands (use with care).",
    )
    parser.add_argument("--version", action="version", version=f"aicoder {__version__}")
    return parser


def _make_approver(config: Config):
    """Return an approver that previews a mutating action and asks to proceed."""

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
        return ui.confirm(f"Run {tool.name}?")

    return approver


def _language_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".json": "json",
        ".md": "markdown",
        ".sh": "bash",
        ".html": "html",
        ".css": "css",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
    }.get(ext, "text")


def _repl(agent: Agent) -> int:
    ui.banner(agent.config.model, os.path.abspath(agent.config.workdir))
    while True:
        try:
            message = ui.user_prompt().strip()
        except (EOFError, KeyboardInterrupt):
            ui.newline()
            ui.info("bye")
            return 0

        if not message:
            continue
        if message in ("/exit", "/quit"):
            ui.info("bye")
            return 0
        if message == "/reset":
            agent.reset()
            ui.info("conversation cleared")
            continue

        try:
            agent.send(message)
        except AgentError as exc:
            ui.error(str(exc))
        except KeyboardInterrupt:
            ui.newline()
            ui.info("[interrupted]")


def _one_shot(agent: Agent, prompt: str) -> int:
    try:
        agent.send(prompt)
        return 0
    except AgentError as exc:
        ui.error(str(exc))
        return 1
    except KeyboardInterrupt:
        ui.newline()
        return 130


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if not has_api_key():
        ui.error(
            "No API credentials found. Set ANTHROPIC_API_KEY in your environment "
            "(see .env.example) and try again."
        )
        return 2

    config = Config.from_env(
        model=args.model,
        max_tokens=args.max_tokens,
        workdir=args.workdir,
        auto_approve=args.yes,
    )

    if not os.path.isdir(config.workdir):
        ui.error(f"Working directory does not exist: {config.workdir}")
        return 2

    try:
        agent = Agent(config, _make_approver(config))
    except Exception as exc:  # e.g. SDK misconfiguration
        ui.error(f"Failed to initialize: {exc}")
        return 2

    if args.prompt:
        return _one_shot(agent, " ".join(args.prompt))
    return _repl(agent)


if __name__ == "__main__":
    sys.exit(main())
