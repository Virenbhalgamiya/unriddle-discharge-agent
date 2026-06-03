from __future__ import annotations

import json
import os

import anthropic

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            timeout=self.timeout_seconds,
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        def _call() -> LLMResponse:
            system = ""
            user_msgs = []
            for m in messages:
                if m.role == "system":
                    system = m.content
                else:
                    user_msgs.append({"role": m.role, "content": m.content})
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or anthropic.NOT_GIVEN,
                messages=user_msgs,
            )
            content = resp.content[0].text if resp.content else ""
            return LLMResponse(content=content, raw=resp, provider=self.name, model=self.model)

        return self._retry_call(_call)

    def structured_complete(
        self,
        messages: list[LLMMessage],
        schema: dict,
        temperature: float = 0.0,
    ) -> dict:
        schema_prompt = (
            "Respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            "Return ONLY JSON, no markdown."
        )
        augmented = messages + [LLMMessage(role="user", content=schema_prompt)]
        response = self.complete(augmented, temperature=temperature, max_tokens=1024)
        text = response.content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return super().structured_complete(messages, schema, temperature)
