from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    content: str
    raw: Any = None
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    retries: int = 0


@dataclass
class LLMMessage:
    role: str
    content: str


class BaseLLMProvider(ABC):
    """Provider-agnostic LLM interface."""

    name: str = "base"
    max_retries: int = 3
    timeout_seconds: float = 60.0

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        raise NotImplementedError

    def structured_complete(
        self,
        messages: list[LLMMessage],
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        schema_prompt = (
            "Respond with valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            "Return ONLY JSON, no markdown."
        )
        augmented = messages + [LLMMessage(role="user", content=schema_prompt)]
        response = self.complete(augmented, temperature=temperature)
        text = response.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def _retry_call(self, func, *args, **kwargs) -> LLMResponse:
        last_error: Optional[Exception] = None
        retries = 0
        for attempt in range(self.max_retries):
            try:
                start = time.time()
                result = func(*args, **kwargs)
                result.latency_ms = (time.time() - start) * 1000
                result.retries = retries
                return result
            except Exception as exc:
                last_error = exc
                retries += 1
                if attempt < self.max_retries - 1:
                    delay = 0.5 * (attempt + 1)
                    err_text = str(exc).lower()
                    if "429" in err_text or "quota" in err_text or "resourceexhausted" in err_text:
                        delay = min(30.0, 2.0 * (attempt + 1))
                    time.sleep(delay)
        raise RuntimeError(f"LLM call failed after {self.max_retries} retries: {last_error}")
