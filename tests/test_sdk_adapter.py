"""Tests for the LLM SDK adapter."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, cast

import pytest

from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.base.sdk import BaseLLMSDK, GenerationConfig, GenerationResponse, Message, ToolCall


class FakeSDK(BaseLLMSDK):
    """Minimal SDK stub for adapter tests."""

    def __init__(self):
        super().__init__(api_key="test-key", base_url="https://example.invalid")
        self.last_stream = None

    @property
    def client(self):
        return None

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        self.last_stream = stream
        return GenerationResponse(
            content="plain response",
            model=config.model,
            finish_reason="stop",
        )

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        self.last_stream = stream
        if stream:
            async def _stream() -> AsyncGenerator[dict[str, str], None]:
                yield {"type": "text", "content": "streamed"}

            return _stream()

        return GenerationResponse(
            content="tool response",
            model=config.model,
            finish_reason="stop",
            tool_calls=[
                ToolCall(id="call_1", name="lookup", arguments='{"query":"jarvis"}')
            ],
            reasoning_content="thinking",
            usage={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
            metadata={"source": "fake"},
        )

    def get_available_models(self) -> list[str]:
        return ["fake-model"]


@pytest.mark.asyncio
async def test_generate_with_tools_returns_mapping_with_model() -> None:
    """The adapter should normalize SDK responses into the dict shape the agent expects."""
    adapter = SDKAdapter(FakeSDK(), provider_name="fake")

    result = cast(
        dict[str, Any],
        await adapter.generate_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"function": {"name": "lookup", "parameters": {}}}],
            model="gpt-test",
        ),
    )

    assert isinstance(result, dict)
    assert result["content"] == "tool response"
    assert result["model"] == "gpt-test"
    assert result["finish_reason"] == "stop"
    assert result["reasoning_content"] == "thinking"
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
    assert result["metadata"] == {"source": "fake"}
    assert result["tool_calls"][0]["function"]["name"] == "lookup"
    assert result["tool_calls"][0]["function"]["arguments"] == '{"query":"jarvis"}'


@pytest.mark.asyncio
async def test_generate_with_tools_streams_through_when_requested() -> None:
    """The adapter should preserve streamed tool responses instead of normalizing them."""
    adapter = SDKAdapter(FakeSDK(), provider_name="fake")

    stream = cast(
        AsyncGenerator[Any, None],
        await adapter.generate_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"function": {"name": "lookup", "parameters": {}}}],
            model="gpt-test",
            stream=True,
        ),
    )

    assert hasattr(stream, "__aiter__")
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    assert chunks == [{"type": "text", "content": "streamed"}]


@pytest.mark.asyncio
async def test_generate_returns_plain_text() -> None:
    """The plain generation path should still return content as a string."""
    adapter = SDKAdapter(FakeSDK(), provider_name="fake")

    result = await adapter.generate(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-test",
    )

    assert result == "plain response"
