"""Terminal presentation, kept in one place so the agent stays logic-only.

Uses `rich` when available and degrades to plain print otherwise, so the tool
still works in a bare environment.
"""

from __future__ import annotations

import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text

    _console: Optional["Console"] = Console()
    _err_console: Optional["Console"] = Console(stderr=True)
except Exception:  # pragma: no cover - rich should be installed
    _console = None
    _err_console = None


def _plain(*parts: str, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    print("".join(parts), file=stream)


APP_NAME = "DCS Code CLI"

# ASCII "dcs", echoing the lowercase wordmark in the DCS Corp logo.
_SPLASH_ART = r"""
      _
   __| | ___ ___
  / _` |/ __/ __|
 | (_| | (__\__ \
  \__,_|\___|___/
"""


TAGLINE = "Brought to you by the AI for Software Engineers Working Group"


def splash() -> None:
    """Print the DCS Code CLI splash screen."""
    if _console:
        _console.print(Text(_SPLASH_ART.strip("\n"), style="bold cyan"))
        _console.print(Text(APP_NAME, style="bold cyan"))
        _console.print(Text(TAGLINE, style="dim"))
    else:
        _plain(_SPLASH_ART.strip("\n"))
        _plain(APP_NAME)
        _plain(TAGLINE)


def banner(model: str, workdir: str, hint: str = "") -> None:
    splash()
    if _console:
        body = Text.assemble(
            ("model: ", "dim"), (model, "green"),
            ("\nworkdir: ", "dim"), (workdir, "green"),
            ("\n\nType your request. ", ""),
            ("/help", "yellow"), (" for commands, ", ""),
            ("/exit", "yellow"), (" to quit.", ""),
        )
        if hint:
            body.append("\n" + hint, style="magenta")
        _console.print(Panel.fit(body, border_style="cyan"))
    else:
        _plain(f"model={model} workdir={workdir}")
        _plain("Type your request. /help for commands, /exit to quit.")
        if hint:
            _plain(hint)


def user_prompt() -> str:
    if _console:
        return _console.input("[bold cyan]you ›[/] ")
    return input("you › ")


def assistant_prefix() -> None:
    if _console:
        _console.print("[bold green]aicoder ›[/] ", end="")
    else:
        _plain("aicoder › ")


def stream_text(chunk: str) -> None:
    # Stream raw so tokens appear as they arrive; final formatting is deferred.
    sys.stdout.write(chunk)
    sys.stdout.flush()


def newline() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()


def tool_call(summary: str) -> None:
    if _console:
        _console.print(f"  [magenta]⚙[/] [dim]{summary}[/]")
    else:
        _plain(f"  * {summary}")


def tool_result(name: str, ok: bool, preview: str) -> None:
    preview = preview.strip().splitlines()[0] if preview.strip() else ""
    if len(preview) > 80:
        preview = preview[:80] + "…"
    mark = "[green]✓[/]" if ok else "[red]✗[/]"
    if _console:
        _console.print(f"    {mark} [dim]{preview}[/]")
    else:
        _plain(f"    {'ok' if ok else 'ERR'}: {preview}")


def diff_preview(title: str, body: str, language: str = "text") -> None:
    if _console:
        _console.print(
            Panel(Syntax(body, language, word_wrap=True), title=title, border_style="yellow")
        )
    else:
        _plain(f"--- {title} ---")
        _plain(body)


def _ask(question: str, hint: str) -> str:
    if _console:
        return _console.input(f"[yellow]{question}[/] [dim]{hint}[/] ").strip().lower()
    return input(f"{question} {hint} ").strip().lower()


def confirm(question: str, default: bool = True) -> bool:
    """A yes/no prompt. Enter accepts the default (Yes unless default=False)."""
    hint = "[Y/n]" if default else "[y/N]"
    answer = _ask(question, hint)
    if not answer:
        return default
    return answer in ("y", "yes")


def approve(question: str) -> str:
    """A three-way approval prompt. Returns 'yes', 'no', or 'always'.

    Enter defaults to yes; 'a'/'always' approves this action type for the rest
    of the session.
    """
    answer = _ask(question, "[Y/n/a]")
    if not answer or answer in ("y", "yes"):
        return "yes"
    if answer in ("a", "always", "all"):
        return "always"
    return "no"


def info(message: str) -> None:
    if _console:
        _console.print(f"[dim]{message}[/]")
    else:
        _plain(message)


def error(message: str) -> None:
    if _err_console:
        _err_console.print(f"[bold red]error:[/] {message}")
    else:
        _plain(f"error: {message}", err=True)
