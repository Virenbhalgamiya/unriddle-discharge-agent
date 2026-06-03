import os

import pytest
from dotenv import load_dotenv

from app.llm.base_provider import LLMMessage
from app.llm.provider_factory import get_provider


@pytest.mark.live
def test_gemini_live_structured_complete():
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    provider = get_provider("gemini", fallback_to_mock=False)
    try:
        result = provider.structured_complete(
            messages=[
                LLMMessage(role="user", content="Choose the next clinical agent tool."),
            ],
            schema={
                "type": "object",
                "properties": {
                    "next_tool": {"type": "string"},
                    "reasoning_summary": {"type": "string"},
                },
                "required": ["next_tool", "reasoning_summary"],
            },
        )
    except RuntimeError as exc:
        if "429" in str(exc) or "quota" in str(exc).lower():
            pytest.skip(f"Gemini quota exceeded: {exc}")
        raise

    assert "next_tool" in result
    assert "reasoning_summary" in result
    assert provider.model_name == "gemini-3.5-flash"
