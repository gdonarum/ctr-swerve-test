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

    # GitLab (on-prem). Project is supplied per call; this is an optional default.
    gitlab_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    gitlab_project: Optional[str] = None

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
