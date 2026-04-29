from __future__ import annotations

import os

from .anthropic_provider import AnthropicProvider
from .base import Provider
from .openai_provider import OpenAIProvider

PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

DEFAULT_PROVIDER_NAME: str = os.environ.get("EXTRACTOR_PROVIDER", "anthropic")


def list_providers() -> list[str]:
    return list(PROVIDERS.keys())


def get_provider(name: str | None = None) -> Provider:
    name = name or DEFAULT_PROVIDER_NAME
    if name not in PROVIDERS:
        raise ValueError(f"unknown provider '{name}'; available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]()
