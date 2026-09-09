"""LLM backend: an OpenAI-compatible client pointed at a LiteLLM proxy.

LiteLLM exposes an OpenAI-compatible API, so we use the official ``openai`` SDK
with a custom ``base_url`` and the user's per-user API key. This gives us model
listing (``/models``) and streaming chat completions with tool calling for free.
"""

from __future__ import annotations

from typing import List

from openai import OpenAI

from aicoder.config import Config


class LLMError(Exception):
    """A user-facing error talking to the LiteLLM backend."""


def make_client(config: Config) -> OpenAI:
    """Construct an OpenAI client bound to the LiteLLM endpoint."""
    if not config.has_llm_credentials():
        raise LLMError(
            "LiteLLM is not configured. Set LITELLM_BASE_URL and LITELLM_API_KEY."
        )
    return OpenAI(base_url=config.base_url, api_key=config.api_key)


def list_models(client: OpenAI) -> List[str]:
    """Return the sorted list of model ids the LiteLLM proxy exposes."""
    try:
        page = client.models.list()
    except Exception as exc:  # network / auth / proxy errors
        raise LLMError(f"Could not list models: {exc}") from exc
    return sorted(m.id for m in page.data)
