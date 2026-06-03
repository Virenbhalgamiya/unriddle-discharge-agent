from __future__ import annotations

import os

import httpx

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class HuggingFaceProvider(BaseLLMProvider):
    name = "huggingface"

    def __init__(self) -> None:
        self.token = os.getenv("HUGGINGFACE_API_TOKEN", "")
        self.model_id = os.getenv(
            "HUGGINGFACE_MODEL_ID", "microsoft/Phi-3-mini-4k-instruct"
        )
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        def _call() -> LLMResponse:
            prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "temperature": temperature,
                    "max_new_tokens": max_tokens,
                    "return_full_text": False,
                },
            }
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(self.api_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            if isinstance(data, list) and data:
                content = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                content = data.get("generated_text", str(data))
            else:
                content = str(data)
            return LLMResponse(content=content, raw=data, provider=self.name, model=self.model_id)

        return self._retry_call(_call)
