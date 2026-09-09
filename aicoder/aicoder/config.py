"""Runtime configuration for aicoder.

Configuration is resolved once from CLI flags and environment variables, then
passed around explicitly so the rest of the code never touches ``os.environ``.

The LLM backend is a LiteLLM proxy (an OpenAI-compatible HTTPS endpoint where
each user has their own API key). GitLab (on-prem) is used for issue tracking.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# A generous output ceiling per response. Streaming is always on, so a large
# value here does not risk an HTTP timeout.
DEFAULT_MAX_TOKENS = 16000

# Stop the agent from looping forever if something goes wrong.
DEFAULT_MAX_TURNS = 50


def _first_env(*names: str) -> Optional[str]:
    """Return the first non-empty environment variable among ``names``."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def load_dotenv(path: str = ".env", override: bool = False) -> bool:
    """Load ``KEY=value`` pairs from a .env file into ``os.environ``.

    A tiny, dependency-free dotenv loader so that copying ``.env.example`` to
    ``.env`` is enough — no need to remember to ``export`` or ``source`` it.
    Lines may start with ``export`` and values may be quoted. Existing
    environment variables win unless ``override`` is True. Returns True if the
    file existed and was read.
    """
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if override or key not in os.environ:
                os.environ[key] = value
    return True


@dataclass
class Config:
    """Resolved configuration for a single aicoder run."""

    # LiteLLM / LLM backend
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_turns: int = DEFAULT_MAX_TURNS

    # Working directory and safety
    workdir: str = "."
    auto_approve: bool = False

    # Autosave the conversation per working directory (resume with --continue).
    autosave: bool = True

    # GitLab (on-prem). Project is supplied per call; this is an optional default.
    gitlab_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    gitlab_project: Optional[str] = None

    # TLS / corporate proxy (e.g. Zscaler). Either point at a CA bundle file, or
    # use the operating system's trust store (where IT usually installs the cert).
    ca_bundle: Optional[str] = None
    use_system_certs: bool = False

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        """Build a Config from the environment, applying explicit overrides.

        Overrides whose value is ``None`` are ignored, so callers can pass raw
        argparse results without clobbering resolved values.
        """
        cfg = cls(
            base_url=_first_env("LITELLM_BASE_URL", "AICODER_BASE_URL", "OPENAI_BASE_URL"),
            api_key=_first_env("LITELLM_API_KEY", "AICODER_API_KEY", "OPENAI_API_KEY"),
            model=_first_env("LITELLM_MODEL", "AICODER_MODEL"),
            gitlab_url=_first_env("GITLAB_URL"),
            gitlab_token=_first_env("GITLAB_TOKEN"),
            gitlab_project=_first_env("GITLAB_PROJECT"),
            ca_bundle=_first_env(
                "AICODER_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"
            ),
            use_system_certs=_env_truthy("AICODER_SYSTEM_CERTS"),
            autosave=not _env_truthy("AICODER_NO_AUTOSAVE"),
        )
        for key, value in overrides.items():
            if value is not None and hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg

    # --- convenience predicates ---------------------------------------------

    def has_llm_credentials(self) -> bool:
        return bool(self.base_url and self.api_key)

    def has_gitlab_credentials(self) -> bool:
        return bool(self.gitlab_url and self.gitlab_token)
