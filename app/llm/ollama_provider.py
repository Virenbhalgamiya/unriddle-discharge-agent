from __future__ import annotations

import os

import httpx

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        def _call() -> LLMResponse:
            payload = {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
            content = data.get("message", {}).get("content", "")
            return LLMResponse(content=content, raw=data, provider=self.name, model=self.model)

        return self._retry_call(_call)
