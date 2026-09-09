# Setting up aicoder on Windows: WSL (Linux) and PowerShell

aicoder is a Python CLI, so it runs anywhere Python 3.10+ does. On Windows you
have two good options:

- **WSL (Ubuntu/Debian on Windows)** — recommended; you get a real Linux shell,
  and `git` and shell commands behave the way the assistant expects.
- **Native PowerShell** — works fine too; a few commands differ.

Both need three things configured:

1. Your **LiteLLM** endpoint URL and your personal API key.
2. (Optional) Your **GitLab** URL, a personal access token, and a default project.
3. Python 3.10 or newer.

---

## Option A — WSL (recommended)

### 1. Install / open WSL

From an elevated PowerShell (first time only):

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted, then open **Ubuntu** from the Start menu. Everything below
runs inside that Ubuntu shell.

### 2. Install Python and git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 --version   # should be 3.10+
```

### 3. Get the code and install

```bash
# from wherever you unzipped/cloned the project
cd aicoder
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Configure your environment

Add these to `~/.bashrc` (so they persist), then `source ~/.bashrc`:

```bash
export LITELLM_BASE_URL="https://litellm.your-company.com"
export LITELLM_API_KEY="sk-your-personal-key"

# optional GitLab (on-prem) integration
export GITLAB_URL="https://gitlab.your-company.com"
export GITLAB_TOKEN="glpat-your-token"          # scope: api
export GITLAB_PROJECT="my-group/my-project"     # optional default project
```

> Tip: instead of editing `~/.bashrc`, you can copy `.env.example` to `.env`,
> fill it in, and run `set -a; source .env; set +a` before launching.

### 5. Run it

```bash
cd /path/to/your/project     # the repo you want to work on
aicoder
```

### Notes for WSL

- Work inside the Linux filesystem (`~/...` or `/home/you/...`) for best
  performance. Editing files under `/mnt/c/...` works but is slower.
- If your company uses a TLS-inspecting proxy, point Python at the corporate CA
  bundle: `export REQUESTS_CA_BUNDLE=/path/to/corp-ca.pem` (also honored by the
  OpenAI SDK via `SSL_CERT_FILE`).

---

## Option B — Native PowerShell

### 1. Install Python and git

Install from the Microsoft Store or [python.org](https://www.python.org/downloads/)
(check "Add python.exe to PATH"), and [Git for Windows](https://git-scm.com/download/win).

```powershell
python --version   # should be 3.10+
git --version
```

### 2. Get the code and install

```powershell
cd aicoder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

> If activation is blocked, allow local scripts for your user:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3. Configure your environment

**For the current session only:**

```powershell
$env:LITELLM_BASE_URL = "https://litellm.your-company.com"
$env:LITELLM_API_KEY  = "sk-your-personal-key"

# optional GitLab
$env:GITLAB_URL     = "https://gitlab.your-company.com"
$env:GITLAB_TOKEN   = "glpat-your-token"
$env:GITLAB_PROJECT = "my-group/my-project"
```

**To persist across sessions** (stored in your user environment):

```powershell
setx LITELLM_BASE_URL "https://litellm.your-company.com"
setx LITELLM_API_KEY  "sk-your-personal-key"
setx GITLAB_URL       "https://gitlab.your-company.com"
setx GITLAB_TOKEN     "glpat-your-token"
setx GITLAB_PROJECT   "my-group/my-project"
```

Close and reopen PowerShell after `setx` for the values to take effect.

### 4. Run it

```powershell
cd C:\path\to\your\project
aicoder
```

### Notes for PowerShell

- The assistant runs shell commands through your default shell. On native
  Windows that means PowerShell/cmd semantics — prefer `dir`, `type`, etc., or
  just use WSL if you want Linux commands.
- Corporate TLS proxy: `setx REQUESTS_CA_BUNDLE "C:\path\to\corp-ca.pem"`.

---

## Verifying your setup

```bash
aicoder --version
aicoder            # then type:  /models
```

`/models` should print the models your LiteLLM proxy exposes. If it errors:

| Symptom | Fix |
| --- | --- |
| `LiteLLM is not configured` | `LITELLM_BASE_URL` / `LITELLM_API_KEY` are not set in this shell. |
| `Authentication failed` | Wrong or expired API key. |
| `Could not list models` / TLS errors | Check the URL, VPN, and CA bundle (see the TLS notes above). |
| `GitLab is not configured` | Set `GITLAB_URL` and `GITLAB_TOKEN` (only needed for issue commands). |

---

## Quick start once it runs

```
/models                     list available models
/model <name>               pick the active model
explain what this repo does
add a --verbose flag to cli.py and run the tests
/commit "add verbose flag"  commit tracked changes
/issues                     list open GitLab issues
/issue 42                   show issue #42
```

Use `-y` / `--yes` to skip confirmation prompts (only when you trust the task
and your work is committed).
