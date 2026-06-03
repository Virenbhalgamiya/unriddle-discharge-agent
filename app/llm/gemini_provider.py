from __future__ import annotations

import os

import google.generativeai as genai

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.model = genai.GenerativeModel(self.model_name)

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_json: bool = False,
    ) -> LLMResponse:
        def _call() -> LLMResponse:
            prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
            config_kwargs: dict = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            if response_json:
                config_kwargs["response_mime_type"] = "application/json"
            resp = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**config_kwargs),
            )
            content = resp.text or ""
            return LLMResponse(content=content, raw=resp, provider=self.name, model=self.model_name)

        return self._retry_call(_call)

    def structured_complete(
        self,
        messages: list[LLMMessage],
        schema: dict,
        temperature: float = 0.0,
    ) -> dict:
        import json

        schema_prompt = (
            "Respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            "Return ONLY JSON, no markdown."
        )
        augmented = messages + [LLMMessage(role="user", content=schema_prompt)]
        response = self.complete(augmented, temperature=temperature, response_json=True)
        text = response.content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return super().structured_complete(messages, schema, temperature)
