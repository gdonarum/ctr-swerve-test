"""Runtime configuration for aicoder.

Everything the agent needs to run is gathered here so the rest of the code can
stay free of environment lookups and magic strings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default model. Per Anthropic's guidance we default to the most capable
# general-purpose model; override with --model or the AICODER_MODEL env var.
DEFAULT_MODEL = "claude-opus-5"

# A generous output ceiling. Streaming is always on (see agent.py), so a large
# value here does not risk an HTTP timeout.
DEFAULT_MAX_TOKENS = 16000

# Stop the agent from looping forever if something goes wrong.
DEFAULT_MAX_TURNS = 50


@dataclass
class Config:
    """Resolved configuration for a single aicoder run."""

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_turns: int = DEFAULT_MAX_TURNS
    workdir: str = "."
    auto_approve: bool = False

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        """Build a Config from the environment, applying explicit overrides.

        Overrides whose value is ``None`` are ignored so callers can pass raw
        argparse results without clobbering defaults.
        """
        model = os.environ.get("AICODER_MODEL", DEFAULT_MODEL)
        cfg = cls(model=model)
        for key, value in overrides.items():
            if value is not None and hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


def has_api_key() -> bool:
    """Return True if a credential the SDK can use appears to be present."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
