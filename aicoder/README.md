# aicoder

A small, self-hostable **AI coding assistant for your terminal**. It talks to
your own **LiteLLM** proxy (so you can use any model your org exposes, with your
own per-user API key), reads and edits files in your project, runs commands,
uses **git**, and works with issues on your **on-prem GitLab** — pausing to ask
before it changes anything.

It's intentionally small and readable, and it has an extensive test suite. See
[`ROADMAP.md`](ROADMAP.md) for where it's headed (goal: match most of what
Claude Code / OpenCode / Codex CLI do, on your own backend).

## Features

- **Agentic loop** — the model decides which tools to call and iterates until the
  task is done, streaming output token-by-token.
- **LiteLLM backend** — OpenAI-compatible; `/models` lists what's available and
  `/model` switches the active one.
- **File tools** — read, list, literal-substring search, create/overwrite, and
  exact-match edits.
- **Shell** — run builds, tests, and linters (with confirmation).
- **Git** — status, diff, log, add, commit (as tools and via `/commit`).
- **GitLab** — list, view, and create issues/tickets (on-prem REST v4), as tools
  and via `/issues` and `/issue`.
- **Human in the loop** — every file write, command, commit, and issue creation
  is previewed and confirmed (bypass with `--yes`).
- **Interactive or one-shot** — a REPL, or a single request as an argument.

## Requirements

- Python 3.10+
- Access to a LiteLLM proxy endpoint and a personal API key
- (Optional) An on-prem GitLab instance + a personal access token (`api` scope)

## Install

```bash
cd aicoder
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Windows users: see the step-by-step
**[WSL + PowerShell setup guide](docs/setup-wsl-powershell.md)**.

## Configure

aicoder reads configuration from the environment (copy `.env.example` to `.env`
as a reference):

```bash
# LiteLLM (required)
export LITELLM_BASE_URL="https://litellm.example.com"
export LITELLM_API_KEY="sk-..."
# export LITELLM_MODEL="gpt-4o"        # optional default model

# GitLab (optional — only for issue commands/tools)
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="glpat-..."
# export GITLAB_PROJECT="group/project" # optional default project
```

`AICODER_*` and `OPENAI_*` are accepted as fallbacks for the LiteLLM base URL and
key.

## Usage

Interactive session (run it from the project you want to work on):

```bash
aicoder
```

```
you › explain what build.gradle does, then add a comment header to it
you › /commit "document build.gradle"
```

One-shot:

```bash
aicoder "write a failing test for parse(), then make it pass"
aicoder --model gpt-4o "summarize the open GitLab issues in group/project"
```

### Slash commands

| Command | Description |
| --- | --- |
| `/models` | List models available on the LiteLLM proxy. |
| `/model [name]` | Show or set the active model. |
| `/commit <message>` | Commit tracked changes. |
| `/issues [project]` | List open GitLab issues. |
| `/issue <iid> [project]` | Show one GitLab issue. |
| `/reset` | Clear the conversation history. |
| `/help` | Show help. |
| `/exit`, `/quit` | Leave. |

Creating issues, staging specific files, running commands, and editing code are
done by just asking (the assistant calls the matching tool and asks you to
confirm).

### Options

| Flag | Description |
| --- | --- |
| `--model MODEL` | Active model id (default: `$LITELLM_MODEL`, else the first available). |
| `--base-url URL` | LiteLLM base URL (default: `$LITELLM_BASE_URL`). |
| `--max-tokens N` | Max output tokens per response (default: 16000). |
| `--workdir DIR` | Directory to operate in (default: current directory). |
| `-y`, `--yes` | Auto-approve writes, commands, commits, and issue creation. |
| `--version` | Print version and exit. |

## How it works

```
your prompt ──▶ model (LiteLLM chat completions, streaming)
                   │
                   ├─ text  ─────────────────▶ streamed to your terminal
                   └─ tool_calls ──▶ aicoder runs each tool ──▶ results ──┐
                                     (mutating tools gated by y/N)        │
                   ◀──────────────── loop until the model is done ────────┘
```

Tools: filesystem (`read_file`, `write_file`, `str_replace`, `list_directory`,
`search`), shell (`run_command`), git (`git_status/diff/log/add/commit`), and
GitLab (`gitlab_list_issues/get_issue/create_issue`). Adding a tool is a handler
plus one `Tool(...)` entry in `aicoder/tools.py`.

## Project layout

```
aicoder/
├── pyproject.toml            # packaging + `aicoder` console script + pytest config
├── requirements.txt
├── .env.example
├── README.md
├── ROADMAP.md
├── docs/
│   └── setup-wsl-powershell.md
├── aicoder/
│   ├── __main__.py           # python -m aicoder
│   ├── cli.py                # args, REPL, slash commands, one-shot
│   ├── config.py             # env/flag configuration
│   ├── llm.py                # LiteLLM (OpenAI-compatible) client + model listing
│   ├── agent.py              # streaming agentic loop
│   ├── tools.py              # tool registry + handlers
│   ├── gitops.py             # local git wrappers
│   ├── gitlab.py             # on-prem GitLab REST v4 client
│   └── ui.py                 # terminal presentation (rich, with a plain fallback)
└── tests/                    # pytest suite (no network required)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests mock the LiteLLM and GitLab HTTP calls, so the suite runs fully
offline.

## Safety notes

aicoder can modify files, run arbitrary shell commands, commit code, and create
GitLab issues. By default it asks before every such action. `--yes` disables
those prompts — only use it when you trust the request and your work is committed.

## License

MIT.
