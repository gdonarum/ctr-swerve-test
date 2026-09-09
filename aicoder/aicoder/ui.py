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


def banner(model: str, workdir: str) -> None:
    if _console:
        _console.print(
            Panel.fit(
                Text.assemble(
                    ("aicoder", "bold cyan"),
                    ("  your terminal coding assistant\n\n", "dim"),
                    ("model: ", "dim"),
                    (model, "green"),
                    ("\nworkdir: ", "dim"),
                    (workdir, "green"),
                    ("\n\nType your request. ", ""),
                    ("/exit", "yellow"),
                    (" to quit, ", ""),
                    ("/reset", "yellow"),
                    (" to clear history.", ""),
                ),
                border_style="cyan",
            )
        )
    else:
        _plain(f"aicoder — model={model} workdir={workdir}")
        _plain("Type your request. /exit to quit, /reset to clear history.")


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


def confirm(question: str) -> bool:
    if _console:
        answer = _console.input(f"[yellow]{question}[/] [dim](y/N)[/] ").strip().lower()
    else:
        answer = input(f"{question} (y/N) ").strip().lower()
    return answer in ("y", "yes")


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
