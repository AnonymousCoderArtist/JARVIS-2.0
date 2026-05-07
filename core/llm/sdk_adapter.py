"""SDK adapter to bridge new SDK pattern with existing agent interface"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, cast

from core.llm.base import BaseLLMProvider
from core.llm_sdk.base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    GenerationResponse,
    Message,
)


class TokenUsageTracker:
    """Helper class to track token usage from streaming responses"""

    def __init__(self):
        self.usage: dict[str, int] | None = None

    def update(self, chunk: dict[str, Any]) -> None:
        """Update usage from a chunk - usage is typically in the final chunk"""
        # Handle new format: {"type": "usage", "usage": {...}}
        if chunk.get("type") == "usage" and chunk.get("usage"):
            self.usage = chunk["usage"]
        # Handle old format: {"usage": {...}}
        elif "usage" in chunk and chunk["usage"]:
            self.usage = chunk["usage"]


async def _wrap_stream_with_usage_tracking(
    stream: AsyncGenerator[Any, None],
    usage_tracker: TokenUsageTracker,
) -> AsyncGenerator[Any, None]:
    """Wrap a streaming generator to track token usage from final chunk"""
    async for chunk in stream:
        # Check if this chunk contains usage info (usually in the final chunk)
        usage_tracker.update(chunk)
        yield chunk


class SDKAdapter(BaseLLMProvider):
    """Adapter to make SDK instances compatible with BaseLLMProvider interface"""

    def __init__(self, sdk: BaseLLMSDK, provider_name: str):
        self.sdk = sdk
        self.provider_name = provider_name
        self.last_token_usage: dict[str, int] | None = None

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | AsyncGenerator[Any, None]:
        """Generate using SDK with adapter interface"""
        # Convert dict messages to SDK Message objects, filtering out empty messages
        sdk_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
            if msg.get("content") or msg.get("role") == "system"
        ]

        # Create generation config
        config = GenerationConfig(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Call SDK
        result = await self.sdk.generate(sdk_messages, config, stream)

        if stream:
            # For streaming, wrap the generator to track usage from final chunk
            usage_tracker = TokenUsageTracker()
            wrapped_stream = _wrap_stream_with_usage_tracking(
                cast(AsyncGenerator[Any, None], result),
                usage_tracker
            )
            # Store the usage tracker so we can get usage after stream completes
            self._current_usage_tracker = usage_tracker
            return wrapped_stream
        else:
            # SDK returns a GenerationResponse when not streaming; return content
            gen = cast(GenerationResponse, result)
            # Store actual token usage from provider
            if gen.usage:
                self.last_token_usage = gen.usage
            return gen.content

    def _generation_response_to_dict(self, gen: GenerationResponse) -> dict[str, Any]:
        """Convert a typed SDK response into the mapping shape expected by agents."""
        tool_calls: list[dict[str, Any]] = []
        if gen.tool_calls:
            for tc in gen.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                )

        response: dict[str, Any] = {
            "content": gen.content,
            "model": gen.model,
            "finish_reason": gen.finish_reason,
            "reasoning_content": gen.reasoning_content or "",
        }

        if tool_calls:
            response["tool_calls"] = tool_calls
        if gen.usage is not None:
            response["usage"] = gen.usage
        if gen.metadata is not None:
            response["metadata"] = gen.metadata

        return response

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncGenerator[Any, None]:
        """Generate with tools using SDK with adapter interface"""
        # Convert dict messages to SDK Message objects, filtering out empty messages
        sdk_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
            if msg.get("content") or msg.get("role") == "system"
        ]

        # Create generation config
        config = GenerationConfig(
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
        )

        stream = kwargs.pop("stream", stream)

        # Call SDK
        result = await self.sdk.generate_with_tools(sdk_messages, tools, config, stream=stream)

        if stream:
            # For streaming, wrap the generator to track usage from final chunk
            usage_tracker = TokenUsageTracker()
            wrapped_stream = _wrap_stream_with_usage_tracking(
                cast(AsyncGenerator[Any, None], result),
                usage_tracker
            )
            # Store the usage tracker so we can get usage after stream completes
            self._current_usage_tracker = usage_tracker
            return wrapped_stream
        else:
            gen = cast(GenerationResponse, result)
            # Store actual token usage from provider
            if gen.usage:
                self.last_token_usage = gen.usage
            return self._generation_response_to_dict(gen)

    def get_available_models(self) -> list[str]:
        """Get available models from SDK"""
        return self.sdk.get_available_models()

    def get_and_clear_usage(self) -> dict[str, int] | None:
        """Get the last token usage and clear it (for use after streaming completes)"""
        usage = None

        # Check if there's a usage tracker from streaming
        if hasattr(self, '_current_usage_tracker') and self._current_usage_tracker:
            tracker = self._current_usage_tracker
            if tracker.usage:
                usage = tracker.usage
            # Clear the tracker
            self._current_usage_tracker = None

        # Fall back to last_token_usage (from non-streaming)
        if not usage and self.last_token_usage:
            usage = self.last_token_usage

        return usage
