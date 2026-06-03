from __future__ import annotations

import os

from openai import OpenAI

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=self.timeout_seconds)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
