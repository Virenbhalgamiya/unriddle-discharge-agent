from __future__ import annotations

import os

from openai import AzureOpenAI

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class AzureProvider(BaseLLMProvider):
    name = "azure"

    def __init__(self) -> None:
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            timeout=self.timeout_seconds,
        )
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        def _call() -> LLMResponse:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return LLMResponse(content=content, raw=resp, provider=self.name, model=self.model)

        return self._retry_call(_call)
