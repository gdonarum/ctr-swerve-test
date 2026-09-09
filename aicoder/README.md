# DCS Code CLI

```
      _
   __| | ___ ___
  / _` |/ __/ __|
 | (_| | (__\__ \
  \__,_|\___|___/
```

A small, self-hostable **AI coding assistant for your terminal**. It talks to
your own **LiteLLM** proxy (so you can use any model your org exposes, with your
own per-user API key), reads and edits files in your project, runs commands,
uses **git**, and works with issues and merge requests on your **on-prem
GitLab** — pausing to ask before it changes anything.

It's intentionally small and readable, and it has an extensive test suite. See
[`ROADMAP.md`](ROADMAP.md) for where it's headed (goal: match most of what
Claude Code / OpenCode / Codex CLI do, on your own backend).

> The command is `dcs` (with `aicoder` kept as an alias). The Python package is
> `aicoder` and its env vars use the `LITELLM_*`, `GITLAB_*`, and `AICODER_*`
> prefixes.

## Features

- **Agentic loop** — the model decides which tools to call and iterates until the
  task is done, streaming output token-by-token.
- **LiteLLM backend** — OpenAI-compatible; `/models` lists what's available and
  `/model` switches the active one.
- **File tools** — read, list, literal-substring search, create/overwrite, and
  exact-match edits.
- **Shell** — run builds, tests, and linters (with confirmation).
- **Git** — status, diff, log, add, commit (as tools and via `/commit`).
- **GitLab** — list, view, and create **issues** and **merge requests** (on-prem
  REST v4), as tools and via `/issues`, `/issue`, `/mrs`, `/mr`.
- **Sessions** — save and resume conversations (`/save`, `/resume`, `/sessions`).
- **Corporate TLS / Zscaler** — trust a CA bundle or the OS certificate store.
- **Human in the loop** — every file write, command, commit, and issue/MR
  creation is previewed and confirmed (bypass with `--yes`).
- **Interactive or one-shot** — a REPL, or a single request as an argument.

## Requirements

- Python 3.10+
- Access to a LiteLLM proxy endpoint and a personal API key
- (Optional) An on-prem GitLab instance + a personal access token (`api` scope)

## Install

Install it into a Python virtual environment (recommended — keeps its
dependencies isolated from your system Python):

```bash
cd aicoder
python -m venv .venv          # create the venv (once)
source .venv/bin/activate     # activate it  (Windows: .\.venv\Scripts\Activate.ps1)
pip install -e .
```

The `dcs` command is available **whenever that virtualenv is active**, so
re-activate it in each new shell before running `dcs` (`source .venv/bin/activate`).
Prefer a globally-available command instead? Install with
[pipx](https://pipx.pypa.io/): `pipx install .` from this directory.

Windows users: see the step-by-step
**[WSL + PowerShell setup guide](docs/setup-wsl-powershell.md)**.

## Configure

DCS Code CLI reads configuration from the environment (copy `.env.example` to `.env`
as a reference):

```bash
# LiteLLM (required)
export LITELLM_BASE_URL="https://litellm.example.com"
export LITELLM_API_KEY="sk-..."
# export LITELLM_MODEL="gpt-4o"        # optional default model

# GitLab (optional — for issue/MR commands and tools)
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="glpat-..."
# export GITLAB_PROJECT="group/project" # optional default project
```

`AICODER_*` and `OPENAI_*` are accepted as fallbacks for the LiteLLM base URL and
key.

**`.env` is loaded automatically.** Copy `.env.example` to `.env`, fill it in,
and run `dcs` from that directory — no need to `export` or `source` anything
(real environment variables still take precedence). Point at a different file
with `--env-file path/to/.env`. If you *do* prefer to source it, use
`set -a; source .env; set +a` so the values are exported to the `dcs` process —
a plain `source .env` sets shell variables that child processes don't inherit.

### Behind Zscaler (or another TLS-inspecting proxy)

Zscaler re-signs HTTPS with a corporate root CA that Python doesn't trust by
default, which otherwise causes certificate errors. Pick one:

```bash
# 1) Point at the CA bundle / root cert (PEM). REQUESTS_CA_BUNDLE / SSL_CERT_FILE
#    are honored as fallbacks; --ca-bundle overrides.
export AICODER_CA_BUNDLE=/etc/ssl/certs/zscaler-root.pem

# 2) Or trust the OS certificate store (where IT usually installs the cert):
pip install truststore
export AICODER_SYSTEM_CERTS=1     # or run with --system-certs
```

This applies to both the LiteLLM (LLM) and GitLab connections. See the
[setup guide](docs/setup-wsl-powershell.md#behind-zscaler) for how to export the
Zscaler cert on Windows/WSL.

## Usage

Running `dcs` with no arguments starts an **interactive chat session** (the
default) — run it from the project you want to work on:

```bash
dcs
```

```
you › explain what build.gradle does, then add a comment header to it
you › /commit "document build.gradle"
```

One-shot (pass a prompt as an argument to run a single request and exit):

```bash
dcs "write a failing test for parse(), then make it pass"
dcs --model gpt-4o "summarize the open GitLab issues in group/project"
dcs -c            # resume this directory's autosaved session
```

### Slash commands

| Command | Description |
| --- | --- |
| `/models` | List models available on the LiteLLM proxy. |
| `/model [name]` | Show or set the active model. |
| `/commit <message>` | Commit tracked changes. |
| `/issues [project]` | List open GitLab issues. |
| `/issue <iid> [project]` | Show one GitLab issue. |
| `/mrs [project]` | List open GitLab merge requests. |
| `/mr <iid> [project]` | Show one GitLab merge request. |
| `/save [name]` | Save the current conversation. |
| `/resume <name>` | Resume a saved conversation. |
| `/sessions` | List saved conversations. |
| `/reset` | Clear the conversation history. |
| `/help` | Show help. |
| `/exit`, `/quit` | Leave. |

Creating issues and merge requests, staging specific files, running commands,
and editing code are done by just asking (the assistant calls the matching tool
and asks you to confirm).

Saved sessions live under `~/.aicoder/sessions` (override with
`AICODER_SESSIONS_DIR`).

### Options

| Flag | Description |
| --- | --- |
| `--model MODEL` | Active model id (default: `$LITELLM_MODEL`, else the first available). |
| `--base-url URL` | LiteLLM base URL (default: `$LITELLM_BASE_URL`). |
| `--max-tokens N` | Max output tokens per response (default: 16000). |
| `--workdir DIR` | Directory to operate in (default: current directory). |
| `-c`, `--continue` | Resume this directory's autosaved session on startup. |
| `--no-autosave` | Don't autosave the conversation for this directory. |
| `--ca-bundle PATH` | CA bundle/cert for TLS (e.g. your Zscaler root). |
| `--system-certs` | Trust the OS certificate store (needs `truststore`). |
| `-y`, `--yes` | Auto-approve writes, commands, commits, and issue/MR creation. |
| `--version` | Print version and exit. |

### Autosave

Your conversation is autosaved per working directory after every turn and on
exit, so you can pick up where you left off with `dcs -c` (or `/resume` inside a
session). Disable it with `--no-autosave` or `AICODER_NO_AUTOSAVE=1`.

## How it works

```
your prompt ──▶ model (LiteLLM chat completions, streaming)
                   │
                   ├─ text  ─────────────────▶ streamed to your terminal
                   └─ tool_calls ──▶ dcs runs each tool ──▶ results ──────┐
                                     (mutating tools gated by y/N)        │
                   ◀──────────────── loop until the model is done ────────┘
```

Tools: filesystem (`read_file`, `write_file`, `str_replace`, `list_directory`,
`search`), shell (`run_command`), git (`git_status/diff/log/add/commit`), and
GitLab (`gitlab_list_issues/get_issue/create_issue`,
`gitlab_list_merge_requests/get_merge_request/create_merge_request`). Adding a
tool is a handler plus one `Tool(...)` entry in `aicoder/tools.py`.

## Project layout

```
aicoder/
├── pyproject.toml            # packaging + `dcs`/`aicoder` console scripts + pytest config
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
│   ├── gitlab.py             # on-prem GitLab REST v4 client (issues + MRs)
│   ├── session.py            # save/resume conversations
│   ├── certs.py              # corporate TLS (Zscaler) trust configuration
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

DCS Code CLI can modify files, run arbitrary shell commands, commit code, and create
GitLab issues. By default it asks before every such action. `--yes` disables
those prompts — only use it when you trust the request and your work is committed.

## License

MIT.
