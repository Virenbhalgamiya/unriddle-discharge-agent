from __future__ import annotations

import logging
from typing import Optional

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.azure_provider import AzureProvider
from app.llm.base_provider import BaseLLMProvider
from app.llm.config_loader import load_config
from app.llm.gemini_provider import GeminiProvider
from app.llm.huggingface_provider import HuggingFaceProvider
from app.llm.mock_provider import MockProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "azure": AzureProvider,
    "ollama": OllamaProvider,
    "huggingface": HuggingFaceProvider,
    "mock": MockProvider,
}


def get_provider(name: Optional[str] = None, fallback_to_mock: bool = True) -> BaseLLMProvider:
    config = load_config()
    provider_name = (name or config.get("llm_provider", "openai")).lower()
    cls = PROVIDERS.get(provider_name)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {provider_name}")

    try:
        return cls()
    except Exception as exc:
        logger.warning("Provider %s failed to initialize: %s", provider_name, exc)
        if fallback_to_mock and provider_name != "mock":
            logger.info("Falling back to mock provider")
            return MockProvider()
        raise
