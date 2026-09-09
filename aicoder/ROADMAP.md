# aicoder roadmap

**Vision:** aicoder aims to be a capable, self-hostable terminal coding agent
that works against an organization's own **LiteLLM** proxy and **on-prem GitLab**
— reaching, over time, most of the day-to-day functionality of the best coding
CLIs (Claude Code, OpenCode, Codex CLI, Aider, Cursor CLI) while staying small,
readable, and easy to audit.

The guiding principles:

- **Bring-your-own-backend.** Any model behind LiteLLM; no vendor lock-in.
- **Human in the loop by default.** Nothing that mutates the repo, runs a
  command, or touches GitLab happens without confirmation (until you opt out).
- **Small and legible.** Each capability should be understandable in one sitting
  and covered by tests.

Status legend: ✅ done · 🚧 in progress · ⬜ planned

## Now (v0.2 — shipped)

- ✅ Agentic tool-use loop over a LiteLLM (OpenAI-compatible) endpoint
- ✅ Streaming responses
- ✅ File tools: read, write, exact-match edit, list, literal search
- ✅ Shell command execution with confirmation
- ✅ Git tools: status, diff, log, add, commit
- ✅ GitLab issues: list, get, create (on-prem, REST v4)
- ✅ `/models` and `/model` to discover and switch models
- ✅ `/commit`, `/issues`, `/issue` slash commands
- ✅ Interactive REPL and one-shot mode
- ✅ Extensive pytest suite
- ✅ WSL + PowerShell setup guide

## Next (v0.3 — parity basics)

- ⬜ **Persistent sessions**: save/resume conversation history (`/save`, `/resume`)
- ⬜ **Context management**: token accounting, auto-summarize/compact long histories
- ⬜ **Better diffs**: unified-diff previews and a `apply_patch`-style multi-hunk edit tool
- ⬜ **Project context file**: read an `AICODER.md` / `AGENTS.md` for repo conventions
- ⬜ **`.aicoderignore`** and gitignore-aware search/traversal
- ⬜ **Cost & usage reporting** per turn (tokens in/out, model)
- ⬜ **Config file** (`~/.config/aicoder/config.toml`) in addition to env vars

## Later (v0.4+ — advanced agent features)

- ⬜ **ripgrep-backed search** when available, with regex support
- ⬜ **Sub-agents / task delegation** for large multi-step work
- ⬜ **Planning mode** (propose a plan, get approval, then execute) à la Claude Code
- ⬜ **MCP client support** to reuse the growing tool ecosystem
- ⬜ **GitLab merge requests**: create/list/review MRs, not just issues
- ⬜ **Git branch/worktree helpers** for isolated changes
- ⬜ **Inline citations** linking answers to `file:line`
- ⬜ **Custom slash commands / prompt snippets** defined per project
- ⬜ **Approval policies** (allowlist safe commands, always-ask patterns)
- ⬜ **Hooks** (pre/post tool, pre-commit) for org-specific guardrails

## Reference CLIs we take inspiration from

| Tool | Ideas we want to emulate |
| --- | --- |
| **Claude Code** | Tool-use loop, planning mode, permission prompts, project memory, subagents |
| **OpenCode** | Provider-agnostic backend, clean TUI, session management |
| **Codex CLI** | `apply_patch` editing, sandboxed command execution, approval modes |
| **Aider** | Git-native workflow, repo map, auto-commit with good messages |
| **Cursor CLI** | Fast edit/apply loop, context selection |

## Non-goals (for now)

- A full TUI/graphical interface — the terminal REPL stays the primary surface.
- Bundling model weights or a specific provider — the backend is always LiteLLM.
- Replacing your IDE — aicoder complements it.

Contributions and reordering suggestions welcome; open a GitLab issue (aicoder
can do that for you 🙂).
