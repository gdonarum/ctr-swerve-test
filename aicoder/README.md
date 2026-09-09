# aicoder

A small AI coding assistant that lives in your terminal, powered by the
[Claude API](https://docs.anthropic.com/). Ask it to explain code, make
changes, write new files, or run your tests — it reads and edits files in your
project and runs commands, pausing to ask before it changes anything.

It's intentionally tiny and readable (a few hundred lines), so it's easy to
understand, fork, and extend.

## Features

- **Agentic loop** — Claude decides which tools to call and iterates until the
  task is done.
- **Real tools** — read files, list directories, literal-substring search,
  create/overwrite files, exact-match edits, and run shell commands.
- **Human in the loop** — every file write and shell command is previewed and
  requires your confirmation (unless you pass `--yes`).
- **Streaming** — responses appear token-by-token.
- **Interactive or one-shot** — start a REPL, or pass a request as an argument.

## Install

Requires Python 3.10+.

```bash
cd aicoder
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Or, without installing the console script:

```bash
pip install -r requirements.txt
python -m aicoder
```

## Configure

aicoder authenticates with the standard Anthropic environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

You can copy `.env.example` to `.env` as a reminder, then source it or export
the value yourself. To change the model, set `AICODER_MODEL` or pass `--model`.

## Usage

Interactive session (run it from the project you want to work on):

```bash
aicoder
```

```
you › add a --verbose flag to cli.py and wire it into logging
```

One-shot request:

```bash
aicoder "explain what build.gradle does in this repo"
aicoder "write a failing test for the parse() function, then make it pass"
```

Inside the REPL:

- `/reset` — clear the conversation history
- `/exit` (or `/quit`) — leave

### Options

| Flag | Description |
| --- | --- |
| `--model MODEL` | Model id (default: `claude-opus-5`, or `$AICODER_MODEL`). |
| `--max-tokens N` | Max output tokens per response (default: 16000). |
| `--workdir DIR` | Directory to operate in (default: current directory). |
| `-y`, `--yes` | Auto-approve file writes and shell commands. |
| `--version` | Print the version and exit. |

## How it works

```
your prompt ──▶ Claude (Messages API, streaming)
                   │
                   ├─ text  ──────────────▶ streamed to your terminal
                   └─ tool_use ──▶ aicoder runs the tool ──▶ tool_result ──┐
                                   (write/run gated by a y/N prompt)       │
                   ◀───────────────────────── loop until end_turn ────────┘
```

The whole loop is in `aicoder/agent.py`; the tools are in `aicoder/tools.py`.
Adding a tool is a matter of writing a handler and appending one `Tool(...)`
entry to the registry.

## Project layout

```
aicoder/
├── pyproject.toml        # packaging + `aicoder` console script
├── requirements.txt
├── .env.example
├── README.md
└── aicoder/
    ├── __init__.py
    ├── __main__.py       # `python -m aicoder`
    ├── cli.py            # argument parsing, REPL, one-shot mode
    ├── config.py         # resolved runtime configuration
    ├── agent.py          # the streaming agentic loop
    ├── tools.py          # the tool registry and handlers
    └── ui.py             # terminal presentation (rich, with a plain fallback)
```

## Safety notes

aicoder can modify files and run arbitrary shell commands in the working
directory. By default it asks before every such action. `--yes` disables those
prompts — only use it when you trust the request and have your work committed.

## License

MIT.
