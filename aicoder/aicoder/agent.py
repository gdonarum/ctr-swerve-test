"""The agentic loop: talk to Claude, run the tools it asks for, repeat.

The loop is deliberately explicit (rather than the SDK's beta tool runner) so we
can stream tokens live and gate mutating tools behind a human approval step.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

import anthropic

from aicoder import ui
from aicoder.config import Config
from aicoder.tools import ToolError, describe_call, get_tool, tool_schemas

SYSTEM_PROMPT = """\
You are aicoder, an expert software engineer working inside a user's terminal in \
their project directory. You help by reading and editing files and running \
commands through the provided tools.

Guidelines:
- Investigate before you change anything: read the relevant files and search the \
codebase so your edits fit the existing style and conventions.
- Prefer str_replace for small, targeted edits; use write_file for new files or \
full rewrites.
- Make the smallest change that correctly solves the task. Do not add unrelated \
changes.
- After editing, when it is cheap to do so, verify your work by running the \
project's tests, build, or a linter via run_command.
- Keep your prose concise. Explain what you did and why, not every keystroke.
- If a request is ambiguous or risky, ask a brief clarifying question instead of \
guessing.
"""

# Approver receives the Tool and its parsed args; returns True to proceed.
Approver = Callable[[Any, Dict[str, Any]], bool]


class Agent:
    def __init__(self, config: Config, approver: Approver) -> None:
        self.config = config
        self.approver = approver
        self.client = anthropic.Anthropic()
        self.messages: List[Dict[str, Any]] = []

    def reset(self) -> None:
        self.messages = []

    def send(self, user_message: str) -> None:
        """Run one user turn to completion, streaming output as it arrives."""
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(self.config.max_turns):
            response = self._stream_once()

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                reason = getattr(details, "explanation", None) or "(no explanation)"
                ui.error(f"The model declined to respond: {reason}")
                return

            self.messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # end_turn (or max_tokens) with no tool calls: the turn is over.
                if response.stop_reason == "max_tokens":
                    ui.info("[output truncated at max_tokens]")
                return

            tool_results = [self._run_tool(block) for block in tool_uses]
            self.messages.append({"role": "user", "content": tool_results})

        ui.error(f"Stopped after {self.config.max_turns} turns without finishing.")

    # --- internals ----------------------------------------------------------

    def _stream_once(self):
        """One API call, streaming text to the terminal. Returns the message."""
        printed_prefix = False
        try:
            with self.client.messages.stream(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=tool_schemas(),
                messages=self.messages,
            ) as stream:
                for text in stream.text_stream:
                    if not printed_prefix:
                        ui.assistant_prefix()
                        printed_prefix = True
                    ui.stream_text(text)
                if printed_prefix:
                    ui.newline()
                return stream.get_final_message()
        except anthropic.APIStatusError as exc:
            if printed_prefix:
                ui.newline()
            raise AgentError(_format_api_error(exc)) from exc
        except anthropic.APIConnectionError as exc:
            if printed_prefix:
                ui.newline()
            raise AgentError(f"Network error talking to the API: {exc}") from exc

    def _run_tool(self, block) -> Dict[str, Any]:
        name = block.name
        args = block.input if isinstance(block.input, dict) else {}
        tool = get_tool(name)

        ui.tool_call(describe_call(name, args))

        if tool is None:
            ui.tool_result(name, ok=False, preview="unknown tool")
            return _result(block.id, f"Error: unknown tool {name!r}.", is_error=True)

        if tool.mutating and not self.config.auto_approve:
            if not self.approver(tool, args):
                ui.tool_result(name, ok=False, preview="declined by user")
                return _result(
                    block.id,
                    "The user declined to run this action. Stop and ask how to proceed.",
                    is_error=True,
                )

        try:
            output = tool.handler(args, self.config.workdir)
            ui.tool_result(name, ok=True, preview=output)
            return _result(block.id, output)
        except ToolError as exc:
            ui.tool_result(name, ok=False, preview=str(exc))
            return _result(block.id, f"Error: {exc}", is_error=True)
        except Exception as exc:  # defensive: never crash the loop on a tool bug
            ui.tool_result(name, ok=False, preview=str(exc))
            return _result(block.id, f"Error: {type(exc).__name__}: {exc}", is_error=True)


class AgentError(Exception):
    """A fatal error for the current turn, with a user-facing message."""


def _result(tool_use_id: str, content: str, is_error: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
    }
    if is_error:
        result["is_error"] = True
    return result


def _format_api_error(exc: "anthropic.APIStatusError") -> str:
    if exc.status_code == 401:
        return "Authentication failed. Check your ANTHROPIC_API_KEY."
    if exc.status_code == 404:
        return "Model not found. Check the --model value."
    if exc.status_code == 429:
        return "Rate limited by the API. Wait a moment and try again."
    return f"API error ({exc.status_code}): {getattr(exc, 'message', exc)}"
