from __future__ import annotations

import json
from typing import Any

from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class MockProvider(BaseLLMProvider):
    """Deterministic fallback provider for tests and API failures."""

    name = "mock"

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        last = messages[-1].content if messages else ""
        if "next_tool" in last or "tool" in last.lower():
            content = json.dumps(
                {
                    "next_tool": "detect_missing_fields",
                    "reasoning_summary": "Mock planner selecting next deterministic tool.",
                }
            )
        elif "audit" in last.lower():
            content = json.dumps({"passed": True, "failures": []})
        else:
            content = json.dumps({"status": "ok", "message": "mock response"})
        return LLMResponse(content=content, provider=self.name, model="mock")

    def structured_complete(
        self,
        messages: list[LLMMessage],
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        props = schema.get("properties", {})
        result: dict[str, Any] = {}
        for key, spec in props.items():
            t = spec.get("type", "string")
            if t == "boolean":
                result[key] = True
            elif t == "array":
                result[key] = []
            elif t == "object":
                result[key] = {}
            else:
                result[key] = f"mock_{key}"
        if "next_tool" in props:
            result["next_tool"] = "detect_missing_fields"
        if "passed" in props:
            result["passed"] = True
        if "failures" in props:
            result["failures"] = []
        return result
