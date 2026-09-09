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

> The command is `dcs-code` (with `dcs` and `aicoder` kept as aliases). The
> Python package is `aicoder` and its env vars use the `LITELLM_*`, `GITLAB_*`,
> and `AICODER_*` prefixes.

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

The `dcs-code` command is available **whenever that virtualenv is active**, so
re-activate it in each new shell before running `dcs-code` (`source .venv/bin/activate`).
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

The GitLab **project** is resolved in this order: the value you pass to a
command/tool → `$GITLAB_PROJECT` → the git `origin` remote of the directory you
run `dcs-code` in. So inside a checked-out GitLab repo, `/issues` and "are there open
tickets for this project?" just work without configuring anything.

`AICODER_*` and `OPENAI_*` are accepted as fallbacks for the LiteLLM base URL and
key.

**`.env` is loaded automatically.** Copy `.env.example` to `.env`, fill it in,
and run `dcs-code` from that directory — no need to `export` or `source` anything
(real environment variables still take precedence). Point at a different file
with `--env-file path/to/.env`. If you *do* prefer to source it, use
`set -a; source .env; set +a` so the values are exported to the `dcs-code` process —
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

Running `dcs-code` with no arguments starts an **interactive chat session** (the
default) — run it from the project you want to work on:

```bash
dcs-code
```

```
you › explain what build.gradle does, then add a comment header to it
you › /commit "document build.gradle"
```

One-shot (pass a prompt as an argument to run a single request and exit):

```bash
dcs-code "write a failing test for parse(), then make it pass"
dcs-code --model gpt-4o "summarize the open GitLab issues in group/project"
dcs-code -c            # resume this directory's autosaved session
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
| `/exit`, `/quit`, `exit` | Leave (Ctrl-D also works). |

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
exit, so you can pick up where you left off with `dcs-code -c` (or `/resume` inside a
session). Disable it with `--no-autosave` or `AICODER_NO_AUTOSAVE=1`.

## How it works

```
your prompt ──▶ model (LiteLLM chat completions, streaming)
                   │
                   ├─ text  ─────────────────▶ streamed to your terminal
                   └─ tool_calls ──▶ dcs-code runs each tool ──▶ results ──────┐
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
├── pyproject.toml            # packaging + `dcs-code` console script (+ `dcs`/`aicoder` aliases)
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

## Building & distributing

DCS Code CLI is a standard Python package (`dcs-code-cli`), so you build it once
and hand others a wheel — they don't need this source tree.

**1. Build the artifacts** (a wheel + source archive into `dist/`):

```bash
pip install build
python -m build
# -> dist/dcs_code_cli-<version>-py3-none-any.whl
#    dist/dcs_code_cli-<version>.tar.gz
```

**2. Others install it.** Share the `.whl` (email, shared drive, GitLab release
asset) and they install into their own environment:

```bash
pipx install dcs_code_cli-0.3.0-py3-none-any.whl   # recommended: isolated, on PATH
# or:  pip install dcs_code_cli-0.3.0-py3-none-any.whl
```

That puts the `dcs-code` command on their PATH. They still set their own
`LITELLM_*` / `GITLAB_*` environment (each user has their own keys).

**3. Or publish to an internal index** so people can `pip install dcs-code-cli`
by name. For a GitLab Package Registry (PyPI-style):

```bash
pip install twine
TWINE_PASSWORD=<token> TWINE_USERNAME=<user> \
  twine upload --repository-url https://gitlab.example.com/api/v4/projects/<id>/packages/pypi dist/*
```

Consumers then point pip at that index (`pip install --index-url … dcs-code-cli`)
or add it to their `pip.conf`.

**Standalone binary (no Python required).** If some users don't have Python,
bundle a single executable with [PyInstaller](https://pyinstaller.org/) or
[shiv](https://shiv.readthedocs.io/):

```bash
pip install pyinstaller
pyinstaller --onefile --name dcs-code -c aicoder/__main__.py
# -> dist/dcs-code  (a self-contained executable for THIS OS/arch)
```

Build the binary on each target OS (Linux/macOS/Windows) you need to support.

To cut a new version, bump `version` in `pyproject.toml` and `__version__` in
`aicoder/__init__.py`, then rebuild.

## Approvals

Every mutating action (file writes, edits, shell commands, commits, issue/MR
creation) is previewed and confirmed with a `[Y/n/a]` prompt:

- **Enter or `y`** — approve this one (Yes is the default).
- **`n`** — decline.
- **`a`** — approve **and stop asking** for that action type for the rest of the
  session (answer `a` once to a file write and further writes won't prompt).

Prefer no prompts at all? Start with `-y` / `--yes` to auto-approve everything —
only when you trust the request and your work is committed.

## Safety notes

DCS Code CLI can modify files, run arbitrary shell commands, commit code, and
create GitLab issues/MRs. It asks before every such action by default; `a`
(sticky) and `--yes` relax that at your discretion.

## License

MIT.
