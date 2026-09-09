"""The agentic loop: talk to the model (via LiteLLM), run the tools it asks
for, and repeat until it is done.

The loop is deliberately explicit (rather than a higher-level runner) so we can
stream tokens live and gate mutating tools behind a human approval step. It
speaks the OpenAI chat-completions protocol, which LiteLLM implements.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

import openai

from aicoder import llm, ui
from aicoder.config import Config
from aicoder.tools import ToolError, describe_call, get_tool, tool_schemas

SYSTEM_PROMPT = """\
You are aicoder, an expert software engineer working inside a user's terminal in \
their project directory. You help by reading and editing files, running commands, \
using git, and working with GitLab issues through the provided tools.

Guidelines:
- Investigate before you change anything: read the relevant files and search the \
codebase so your edits fit the existing style and conventions.
- Prefer str_replace for small, targeted edits; use write_file for new files or \
full rewrites.
- Make the smallest change that correctly solves the task. Do not add unrelated \
changes.
- After editing, when it is cheap to do so, verify your work by running the \
project's tests, build, or a linter via run_command.
- Use git tools to inspect and commit changes when the user asks. Write clear, \
conventional commit messages.
- Keep your prose concise. Explain what you did and why, not every keystroke.
- If a request is ambiguous or risky, ask a brief clarifying question instead of \
guessing.
"""

# Approver receives the Tool and its parsed args; returns True to proceed.
Approver = Callable[[Any, Dict[str, Any]], bool]


class AgentError(Exception):
    """A fatal error for the current turn, with a user-facing message."""


class Agent:
    def __init__(self, config: Config, approver: Approver, client=None) -> None:
        self.config = config
        self.approver = approver
        self.client = client if client is not None else llm.make_client(config)
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def send(self, user_message: str) -> None:
        """Run one user turn to completion, streaming output as it arrives."""
        if not self.config.model:
            raise AgentError("No model selected. Use /model to choose one, or set --model.")
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(self.config.max_turns):
            text, tool_calls = self._stream_once()

            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": text or None}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]},
                    }
                    for tc in tool_calls
                ]
            self.messages.append(assistant_msg)

            if not tool_calls:
                return  # model produced a final answer

            for tc in tool_calls:
                result = self._run_tool(tc["id"], tc["name"], tc["args"])
                self.messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )

        ui.error(f"Stopped after {self.config.max_turns} turns without finishing.")

    # --- internals ----------------------------------------------------------

    def _stream_once(self):
        """One streamed API call. Returns (text, list_of_tool_call_dicts)."""
        printed_prefix = False
        content_parts: List[str] = []
        # tool calls arrive fragmented across chunks, keyed by their index.
        calls: Dict[int, Dict[str, str]] = {}

        try:
            stream = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.messages,
                tools=tool_schemas(),
                stream=True,
                max_tokens=self.config.max_tokens,
            )
            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                delta = choice.delta
                if getattr(delta, "content", None):
                    if not printed_prefix:
                        ui.assistant_prefix()
                        printed_prefix = True
                    ui.stream_text(delta.content)
                    content_parts.append(delta.content)
                for tc in getattr(delta, "tool_calls", None) or []:
                    slot = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
        except openai.APIStatusError as exc:
            if printed_prefix:
                ui.newline()
            raise AgentError(_format_api_error(exc)) from exc
        except openai.APIConnectionError as exc:
            if printed_prefix:
                ui.newline()
            raise AgentError(f"Network error talking to LiteLLM: {exc}") from exc

        if printed_prefix:
            ui.newline()

        ordered = [calls[i] for i in sorted(calls)]
        return "".join(content_parts), ordered

    def _run_tool(self, tool_call_id: str, name: str, raw_args: str) -> str:
        args = _parse_args(raw_args)
        tool = get_tool(name)

        if isinstance(args, _ArgError):
            ui.tool_call(name)
            ui.tool_result(name, ok=False, preview="invalid arguments")
            return f"Error: could not parse tool arguments as JSON: {args.detail}"

        ui.tool_call(describe_call(name, args))

        if tool is None:
            ui.tool_result(name, ok=False, preview="unknown tool")
            return f"Error: unknown tool {name!r}."

        if tool.mutating and not self.config.auto_approve:
            if not self.approver(tool, args):
                ui.tool_result(name, ok=False, preview="declined by user")
                return "The user declined to run this action. Stop and ask how to proceed."

        try:
            output = tool.handler(args, self.config)
            ui.tool_result(name, ok=True, preview=output)
            return output
        except ToolError as exc:
            ui.tool_result(name, ok=False, preview=str(exc))
            return f"Error: {exc}"
        except KeyError as exc:
            ui.tool_result(name, ok=False, preview=f"missing arg {exc}")
            return f"Error: missing required argument {exc}."
        except Exception as exc:  # defensive: never crash the loop on a tool bug
            ui.tool_result(name, ok=False, preview=str(exc))
            return f"Error: {type(exc).__name__}: {exc}"


class _ArgError:
    def __init__(self, detail: str) -> None:
        self.detail = detail


def _parse_args(raw_args: str):
    """Parse a tool-call argument string. Empty means no args."""
    if not raw_args or not raw_args.strip():
        return {}
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError as exc:
        return _ArgError(str(exc))
    return parsed if isinstance(parsed, dict) else _ArgError("arguments were not a JSON object")


def _format_api_error(exc: "openai.APIStatusError") -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "Authentication failed. Check your LITELLM_API_KEY."
    if status == 404:
        return "Model or endpoint not found. Check --model and LITELLM_BASE_URL."
    if status == 429:
        return "Rate limited by the backend. Wait a moment and try again."
    return f"API error ({status}): {getattr(exc, 'message', exc)}"
